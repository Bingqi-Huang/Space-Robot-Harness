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
//   Lookup  jaw()                                                     -> Real jaw angle, rad
//   Lookup  LastCapabilityResult()                                   -> String {capability, success, failure_kind,
//                                                                       failure_reason, evidence}
//   Lookup  LastFailureKind()                                        -> Integer, the last result's failure_kind
//                                                                       (openral_msgs/ExecuteRskill; 0 = success/none,
//                                                                       20 = boundary rejection); typed so a plan can
//                                                                       branch without parsing LastCapabilityResult's JSON
//   Lookup  LastFailureStage()                                       -> String, the last "stage" a staged skill
//                                                                       (pick, place, stow, arm_ready, press, ...)
//                                                                       reported reaching, extracted from its evidence;
//                                                                       "" when the result carried none
// Both are a mechanical read of the last ExecuteCapability result already held for LastCapabilityResult -- no
// per-capability interpretation, no recovery choice: what recovery a kind/stage means belongs in the PLEXIL plan
// library, never here.
// No mission logic: no orderings, retries or recoveries -- those belong in the PLEXIL plan library (the baseline's
// pre-engineered knowledge), never in the adapter.
//

#include "AdapterConfiguration.hh"
#include "AdapterExecInterface.hh"
#include "AdapterFactory.hh"
#include "Command.hh"
#include "CommandHandle.hh"
#include "InterfaceAdapter.hh"
#include "LookupReceiver.hh"
#include "State.hh"
#include "Value.hh"
#include "Array.hh"

#include <cstdio>

#include <rclcpp/rclcpp.hpp>
#include <rclcpp_action/rclcpp_action.hpp>
#include <space_harness_msgs/action/execute_capability.hpp>
#include <space_harness_msgs/srv/query_capability.hpp>

#include <chrono>
#include <mutex>
#include <string>
#include <thread>

using ExecuteCapability = space_harness_msgs::action::ExecuteCapability;
using QueryCapability = space_harness_msgs::srv::QueryCapability;

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

// The last `"stage": "<value>"` field in an evidence JSON blob (a staged skill's evidence carries its stages as an
// ordered array; the last one is where it stopped). A text scan, not a JSON parse: evidence_json's shape is the
// skill's own, and this reads only the one field every staged skill happens to share.
std::string last_stage(std::string const &evidence_json)
{
  static std::string const key = "\"stage\": \"";
  auto pos = evidence_json.rfind(key);
  if (pos == std::string::npos) return "";
  pos += key.size();
  auto end = evidence_json.find('"', pos);
  return end == std::string::npos ? "" : evidence_json.substr(pos, end - pos);
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
      "jaw",
      [this](PLEXIL::State const &, PLEXIL::LookupReceiver *rcvr) {
        std::string value;
        if (!query("jaw", "{}", value)) { rcvr->setUnknown(); return; }
        auto pos = value.find(':');
        if (pos == std::string::npos || value.find("null") != std::string::npos) { rcvr->setUnknown(); return; }
        rcvr->update(static_cast<PLEXIL::Real>(std::stod(value.substr(pos + 1))));
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
      "LastFailureKind",
      [this](PLEXIL::State const &, PLEXIL::LookupReceiver *rcvr) {
        std::lock_guard<std::mutex> lock(mutex_);
        rcvr->update(last_failure_kind_);
      });
    config->registerLookupHandlerFunction(
      "LastFailureStage",
      [this](PLEXIL::State const &, PLEXIL::LookupReceiver *rcvr) {
        std::lock_guard<std::mutex> lock(mutex_);
        rcvr->update(last_failure_stage_);
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
    rclcpp_action::Client<ExecuteCapability>::SendGoalOptions opts;
    opts.goal_response_callback = [cmd, intf](auto handle) {
      intf->handleCommandAck(cmd, handle ? PLEXIL::COMMAND_SENT_TO_SYSTEM : PLEXIL::COMMAND_DENIED);
      intf->notifyOfExternalEvent();
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
        last_failure_kind_ = static_cast<PLEXIL::Integer>(r.failure_kind);
        last_failure_stage_ = last_stage(r.evidence_json);
      }
      intf->handleCommandReturn(cmd, PLEXIL::Value(static_cast<bool>(r.success)));
      intf->handleCommandAck(cmd, r.success ? PLEXIL::COMMAND_SUCCESS : PLEXIL::COMMAND_FAILED);
      intf->notifyOfExternalEvent();
    };
    execute_->async_send_goal(goal, opts);
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
  // thread and stalled the plan).
  bool query(std::string const &q, std::string const &args_json, std::string &value)
  {
    auto req = std::make_shared<QueryCapability::Request>();
    req->query = q;
    req->args_json = args_json;
    auto pending = query_->async_send_request(req);
    if (pending.future.wait_for(std::chrono::seconds(5)) != std::future_status::ready) return false;
    auto response = pending.future.get();
    value = response->value_json;
    return response->success;
  }

  rclcpp::Node::SharedPtr node_;
  rclcpp_action::Client<ExecuteCapability>::SharedPtr execute_;
  rclcpp::Client<QueryCapability>::SharedPtr query_;
  std::unique_ptr<rclcpp::executors::MultiThreadedExecutor> executor_;  // after rclcpp::init
  std::thread spinner_;
  std::mutex mutex_;
  std::string last_result_ = "{}";
  PLEXIL::Integer last_failure_kind_ = 0;
  std::string last_failure_stage_;
};

extern "C" {
void initCapabilityAdapter()
{
  REGISTER_ADAPTER(CapabilityAdapter, "CapabilityAdapter");
}
}
