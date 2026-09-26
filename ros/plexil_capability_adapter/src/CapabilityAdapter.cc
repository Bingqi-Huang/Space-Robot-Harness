// PLEXIL Release 6 interface adapter onto the common capability boundary (execution_plan §11.1, §21.4-21.5).
//
// PLEXIL sees exactly the interface Ours sees, and nothing else:
//   Command <capability>(args...)                                   -> Boolean success
//     every Command without its own handler is a capability of contracts.yaml, its arguments positional in the
//     contract's declared input order (e.g. Boolean Command dock_at_feature(String, Real, Real);)
//   Command ExecuteCapability(String capability, String args_json)  -> Boolean success
//     -> space_harness_msgs/ExecuteCapability on /space/capability/execute (one ExecuteRskill through the runner,
//        safety kernel, HAL; the contract is checked by the server)
//   Lookup  QueryCapability(String query, String args_json)          -> String value_json (UNKNOWN on failure)
//     -> space_harness_msgs/QueryCapability on /space/capability/query
//   Lookup  LastCapabilityResult()                                   -> String {capability, success, failure_kind,
//                                                                       failure_reason, evidence}
//   Lookup  PowerUnit(String unit, String field)                      -> String, one field of that unit in the power
//                                                                       distribution units' telemetry (power_status),
//                                                                       e.g. PowerUnit("pdu_2", "breaker") = "tripped";
//                                                                       UNKNOWN when the field is null -- a typed read
//                                                                       so a plan can branch without parsing JSON
//   Command String RequestOperator(String question)                  -> the operator's answer
//     -> publishes openral_msgs/PromptStamped {text: question, metadata_json: {"request_id"}} on
//        /space/operator/request (the same topic space_runtime/agent.py and baselines/europa/host.py use), the
//        Command stays EXECUTING (no Command Ack yet) until a matching request_id comes back on
//        /space/operator/reply, published by experiments/operator_console/console.py; a plan escalates with this
//        and reads the answer as a plain String -- no mission logic here about when to call it or what the answer
//        means, that is the plan library's.
//   Lookup  MissionGoal(String field)                                -> String, one field of the launcher-supplied
//                                                                       mission goal (env MISSION_GOAL, a JSON object,
//                                                                       e.g. Mission B's {"item", "source", "destination"};
//                                                                       baselines/europa/host.py reads the same variable)
//   Lookup  ItemDescription(String item, String field)               -> String, one field of the baselines' shared item
//                                                                       table (the file named by this adapter's
//                                                                       ItemDescriptions attribute in interface-config.xml,
//                                                                       baselines/item_descriptions.json), keyed by the
//                                                                       item's equipment-catalogue name
// Neither interprets what it carries: the goal is the launcher's, the table the baselines' own authored artifact.
// No failure kind or stage is exposed as a typed Lookup (docs/baselines/authoring_spec.md, locked 2026-09-23: a plan
// branch on them is tier 3, forbidden); LastCapabilityResult still carries the whole raw result.
// No mission logic: no orderings, retries or recoveries -- those belong in the PLEXIL plan library (the baseline's
// pre-engineered knowledge), never in the adapter.
//

#include <iostream>
#include "AdapterConfiguration.hh"
#include "AdapterExecInterface.hh"
#include "AdapterFactory.hh"
#include "Command.hh"
#include "CommandHandle.hh"
#include "CommandImpl.hh"
#include "InterfaceAdapter.hh"
#include "LookupReceiver.hh"
#include "State.hh"
#include "Value.hh"
#include "Array.hh"

#include <cstdio>
#include <cstdlib>
#include <fstream>

#include <rclcpp/rclcpp.hpp>
#include <rclcpp_action/rclcpp_action.hpp>
#include <openral_msgs/msg/prompt_stamped.hpp>
#include <space_harness_msgs/action/execute_capability.hpp>
#include <space_harness_msgs/srv/query_capability.hpp>
#include <nlohmann/json.hpp>

#include <atomic>
#include <chrono>
#include <map>
#include <mutex>
#include <string>
#include <thread>

using ExecuteCapability = space_harness_msgs::action::ExecuteCapability;
using QueryCapability = space_harness_msgs::srv::QueryCapability;
using PromptStamped = openral_msgs::msg::PromptStamped;
namespace { char const *kRequestTopic = "/space/operator/request"; char const *kReplyTopic = "/space/operator/reply"; }

namespace
{
std::string json_escape(std::string const &s);

// One PLEXIL value as JSON (scalars and Real/Integer/Boolean/String arrays); empty on an unsupported/unknown value.
std::string value_json(PLEXIL::Value const &v)
{
  switch (v.valueType()) {
    case PLEXIL::BOOLEAN_TYPE: { bool b; return v.getValue(b) ? (b ? "true" : "false") : ""; }
    case PLEXIL::INTEGER_TYPE: { PLEXIL::Integer i; return v.getValue(i) ? std::to_string(i) : ""; }
    case PLEXIL::REAL_TYPE: {
      PLEXIL::Real r;
      if (!v.getValue(r)) return "";
      char buf[64];
      std::snprintf(buf, sizeof(buf), "%.9g", r);
      return buf;
    }
    case PLEXIL::STRING_TYPE: { PLEXIL::String str; return v.getValue(str) ? "\"" + json_escape(str) + "\"" : ""; }
    case PLEXIL::BOOLEAN_ARRAY_TYPE:
    case PLEXIL::INTEGER_ARRAY_TYPE:
    case PLEXIL::REAL_ARRAY_TYPE:
    case PLEXIL::STRING_ARRAY_TYPE: {
      PLEXIL::Array const *arr;
      if (!v.getValuePointer(arr)) return "";
      std::string out = "[";
      for (size_t i = 0; i < arr->size(); ++i) {
        std::string e = value_json(arr->getElementValue(i));
        if (e.empty()) return "";
        out += (i ? ", " : "") + e;
      }
      return out + "]";
    }
    default:
      return "";
  }
}

std::string json_escape(std::string const &s)
{
  std::string out;
  for (char c : s) {
    if (c == '"' || c == '\\') out.push_back('\\');
    out.push_back(c);
  }
  return out;
}

// The `"<key>": "<value>"` string field in a small flat JSON object (PromptStamped's own metadata_json here) --
// a plain text scan, not a JSON parse. "" when the key is absent.
std::string json_string_field(std::string const &json, std::string const &key)
{
  std::string const needle = "\"" + key + "\"";
  auto pos = json.find(needle);
  if (pos == std::string::npos) return "";
  pos = json.find('"', pos + needle.size());  // opening quote of the value, past the key and the ':'
  if (pos == std::string::npos) return "";
  auto end = json.find('"', pos + 1);
  return end == std::string::npos ? "" : json.substr(pos + 1, end - pos - 1);
}
}  // namespace

class CapabilityAdapter : public PLEXIL::InterfaceAdapter
{
public:
  CapabilityAdapter(PLEXIL::AdapterExecInterface &intf, PLEXIL::AdapterConf *conf)
  : PLEXIL::InterfaceAdapter(intf, conf)
  {
  }

  bool initialize(PLEXIL::AdapterConfiguration *config) override
  {
    if (!rclcpp::ok()) rclcpp::init(0, nullptr);
    node_ = std::make_shared<rclcpp::Node>("plexil_capability_adapter");
    execute_ = rclcpp_action::create_client<ExecuteCapability>(node_, "/space/capability/execute");
    query_ = node_->create_client<QueryCapability>("/space/capability/query");
    request_pub_ = node_->create_publisher<PromptStamped>(kRequestTopic, 10);
    reply_sub_ = node_->create_subscription<PromptStamped>(
      kReplyTopic, 10, [this](PromptStamped::SharedPtr msg) { onOperatorReply(msg); });
    config->registerCommandHandlerFunction(
      "ExecuteCapability",
      [this](PLEXIL::Command *cmd, PLEXIL::AdapterExecInterface *intf) {
        std::vector<PLEXIL::Value> const &args = cmd->getArgValues();
        std::string capability, args_json = "{}";
        if (args.size() < 1 || !args[0].getValue(capability) || (args.size() > 1 && !args[1].getValue(args_json))) {
          intf->handleCommandAck(cmd, PLEXIL::COMMAND_FAILED);
          intf->notifyOfExternalEvent();
          return;
        }
        send(cmd, intf, capability, args_json);
      });
    config->registerCommandHandlerFunction(
      "RequestOperator",
      [this](PLEXIL::Command *cmd, PLEXIL::AdapterExecInterface *intf) { requestOperator(cmd, intf); });
    // every other Command is a capability with positional arguments (the Utility adapter's print/pprint keep theirs)
    config->setDefaultCommandHandlerFunction(
      [this](PLEXIL::Command *cmd, PLEXIL::AdapterExecInterface *intf) {
        std::string args_json = "[";
        std::vector<PLEXIL::Value> const &args = cmd->getArgValues();
        for (size_t i = 0; i < args.size(); ++i) {
          std::string e = value_json(args[i]);
          if (e.empty()) {
            intf->handleCommandAck(cmd, PLEXIL::COMMAND_FAILED);
            intf->notifyOfExternalEvent();
            return;
          }
          args_json += (i ? ", " : "") + e;
        }
        send(cmd, intf, cmd->getName(), args_json + "]");
      });
    config->registerLookupHandlerFunction(
      "PowerUnit",
      [this](PLEXIL::State const &state, PLEXIL::LookupReceiver *rcvr) {
        std::string unit, field, value;
        if (state.parameters().size() != 2 || !state.parameter(0).getValue(unit) || !state.parameter(1).getValue(field) ||
            !query("power_status", "{}", value)) { rcvr->setUnknown(); return; }
        auto const v = nlohmann::json::parse(value)["units"][unit][field];
        if (v.is_null()) rcvr->setUnknown();
        else rcvr->update(v.is_string() ? v.get<std::string>() : v.dump());
      });
    config->registerLookupHandlerFunction(
      "QueryCapability",
      [this](PLEXIL::State const &state, PLEXIL::LookupReceiver *rcvr) { queryCapability(state, rcvr); });
    config->registerLookupHandlerFunction(
      "LastCapabilityResult",
      [this](PLEXIL::State const &, PLEXIL::LookupReceiver *rcvr) {
        std::lock_guard<std::mutex> lock(mutex_);
        rcvr->update(last_result_);
      });
    config->registerLookupHandlerFunction(
      "MissionGoal",
      [](PLEXIL::State const &state, PLEXIL::LookupReceiver *rcvr) {
        std::string field;
        state.parameter(0).getValue(field);
        rcvr->update(nlohmann::json::parse(std::getenv("MISSION_GOAL"))[field].get<std::string>());
      });
    config->registerLookupHandlerFunction(
      "ItemDescription",
      [this](PLEXIL::State const &state, PLEXIL::LookupReceiver *rcvr) {
        std::string item, field;
        state.parameter(0).getValue(item);
        state.parameter(1).getValue(field);
        std::ifstream table(getXml().attribute("ItemDescriptions").value());
        rcvr->update(nlohmann::json::parse(table)[item][field].get<std::string>());
      });
    return true;
  }

  bool start() override
  {
    executor_ = std::make_unique<rclcpp::executors::MultiThreadedExecutor>();
    executor_->add_node(node_);
    spinner_ = std::thread([this] { executor_->spin(); });
    // the boundary must be discovered before the first plan call, or requests go nowhere
    return execute_->wait_for_action_server(std::chrono::seconds(30)) &&
           query_->wait_for_service(std::chrono::seconds(30));
  }

  void stop() override
  {
    executor_->cancel();
    if (spinner_.joinable()) spinner_.join();
    rclcpp::shutdown();
  }

private:
  void send(PLEXIL::Command *cmd, PLEXIL::AdapterExecInterface *intf, std::string const &capability,
            std::string const &args_json)
  {
    ExecuteCapability::Goal goal;
    goal.capability = capability;
    goal.args_json = args_json;
    // The plan node <-> capability call join key (§14.6): the id of the Command node that issued this call, the same
    // id the executive's own Node:transition trace prints on this stream (plexil_node_trace.log). Command's public
    // interface has no node; the executive's CommandImpl carries it as its command handle variable's name
    // (xml-parser/parseNode.cc: new CommandImpl(node->getNodeId(), ...); research repo F133).
    std::cout << "[CapabilityAdapter] COMMAND " << static_cast<PLEXIL::CommandImpl *>(cmd)->getAck()->getName() << " "
              << capability << " " << args_json << std::endl;
    rclcpp_action::Client<ExecuteCapability>::SendGoalOptions opts;
    // Only ack a genuine rejection here. PLEXIL's own actionComplete gate (CommandHandleKnown, src/intfc/CommandImpl.cc)
    // is satisfied by ANY known command_handle, terminal or not -- acking COMMAND_SENT_TO_SYSTEM the instant the ROS
    // goal is merely *accepted* (a handshake, not the robot moving) made the executive treat every command as already
    // finished, so the whole plan raced through all its nodes in under a second while the real capability calls were
    // still running (research repo: PLEXIL Mission B live run, 2026-09-22). The command stays EXECUTING, with no ack
    // and no known handle, until the terminal ack below actually arrives.
    opts.goal_response_callback = [cmd, intf](auto handle) {
      if (!handle) {
        intf->handleCommandAck(cmd, PLEXIL::COMMAND_DENIED);
        intf->notifyOfExternalEvent();
      }
    };
    opts.result_callback = [this, cmd, intf, capability](
                             rclcpp_action::ClientGoalHandle<ExecuteCapability>::WrappedResult const &wrapped) {
      auto const &r = *wrapped.result;
      {
        std::lock_guard<std::mutex> lock(mutex_);
        last_result_ = "{\"capability\": \"" + json_escape(capability) + "\", \"success\": " +
                       (r.success ? "true" : "false") + ", \"failure_kind\": " + std::to_string(r.failure_kind) +
                       ", \"failure_reason\": \"" + json_escape(r.failure_reason) + "\", \"evidence\": " +
                       (r.evidence_json.empty() ? "{}" : r.evidence_json) + "}";
      }
      intf->handleCommandReturn(cmd, PLEXIL::Value(static_cast<bool>(r.success)));
      intf->handleCommandAck(cmd, r.success ? PLEXIL::COMMAND_SUCCESS : PLEXIL::COMMAND_FAILED);
      intf->notifyOfExternalEvent();
    };
    execute_->async_send_goal(goal, opts);
  }

  // RequestOperator(String question) -> String answer. No action server/goal handshake here (the console is a plain
  // subscriber): publish the request and leave the command EXECUTING with no ack at all -- see send()'s comment on
  // why an early COMMAND_SENT_TO_SYSTEM ack is wrong, not just superfluous -- until a reply with a matching
  // request_id arrives and onOperatorReply() delivers the one real ack below.
  void requestOperator(PLEXIL::Command *cmd, PLEXIL::AdapterExecInterface *intf)
  {
    std::vector<PLEXIL::Value> const &args = cmd->getArgValues();
    std::string question;
    if (args.size() < 1 || !args[0].getValue(question)) {
      intf->handleCommandAck(cmd, PLEXIL::COMMAND_FAILED);
      intf->notifyOfExternalEvent();
      return;
    }
    std::string request_id = std::to_string(++request_seq_);
    {
      std::lock_guard<std::mutex> lock(mutex_);
      pending_operator_[request_id] = {cmd, intf};
    }
    PromptStamped m;
    m.text = question;
    m.metadata_json = "{\"request_id\": \"" + json_escape(request_id) + "\"}";
    request_pub_->publish(m);
  }

  void onOperatorReply(PromptStamped::SharedPtr msg)
  {
    std::string request_id = json_string_field(msg->metadata_json, "request_id");
    PLEXIL::Command *cmd;
    PLEXIL::AdapterExecInterface *intf;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      auto it = pending_operator_.find(request_id);
      if (it == pending_operator_.end()) return;  // a reply to a report, or one already resolved
      cmd = it->second.first;
      intf = it->second.second;
      pending_operator_.erase(it);
    }
    intf->handleCommandReturn(cmd, PLEXIL::Value(msg->text));
    intf->handleCommandAck(cmd, PLEXIL::COMMAND_SUCCESS);
    intf->notifyOfExternalEvent();
  }

  void queryCapability(PLEXIL::State const &state, PLEXIL::LookupReceiver *rcvr)
  {
    std::string q, args_json = "{}";
    if (state.parameters().size() < 1 || !state.parameter(0).getValue(q) ||
        (state.parameters().size() > 1 && !state.parameter(1).getValue(args_json))) {
      rcvr->setUnknown();
      return;
    }
    std::string value;
    if (query(q, args_json, value)) rcvr->update(value); else rcvr->setUnknown();
  }

  // Humble's async_send_request returns a std::future: get() exactly once (a second get() threw inside the exec
  // thread and stalled the plan). The wait is as long as a loaded host takes to answer: a Lookup that gives up
  // resolves UNKNOWN, and an UNKNOWN SkipCondition runs the node -- a 5 s cap could have named a healthy unit the
  // tripped one with six runs on one host (research repo F114). Past 120 s the boundary is gone.
  bool query(std::string const &q, std::string const &args_json, std::string &value)
  {
    auto req = std::make_shared<QueryCapability::Request>();
    req->query = q;
    req->args_json = args_json;
    auto pending = query_->async_send_request(req);
    if (pending.future.wait_for(std::chrono::seconds(120)) != std::future_status::ready) return false;
    auto response = pending.future.get();
    value = response->value_json;
    return response->success;
  }

  rclcpp::Node::SharedPtr node_;
  rclcpp_action::Client<ExecuteCapability>::SharedPtr execute_;
  rclcpp::Client<QueryCapability>::SharedPtr query_;
  rclcpp::Publisher<PromptStamped>::SharedPtr request_pub_;
  rclcpp::Subscription<PromptStamped>::SharedPtr reply_sub_;
  std::unique_ptr<rclcpp::executors::MultiThreadedExecutor> executor_;  // after rclcpp::init
  std::thread spinner_;
  std::mutex mutex_;
  std::string last_result_ = "{}";
  std::atomic<int> request_seq_{0};
  std::map<std::string, std::pair<PLEXIL::Command *, PLEXIL::AdapterExecInterface *>> pending_operator_;  // request_id -> the Command awaiting its answer
};

extern "C" {
void initCapabilityAdapter()
{
  REGISTER_ADAPTER(CapabilityAdapter, "CapabilityAdapter");
}
}
