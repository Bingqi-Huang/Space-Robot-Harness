// PLEXIL Release 6 interface adapter onto the common capability boundary (execution_plan §11.1, §21.4-21.5).
//
// PLEXIL sees exactly the interface Ours sees, and nothing else:
//   Command ExecuteCapability(String capability, String args_json)  -> Boolean success
//     -> space_harness_msgs/ExecuteCapability on /space/capability/execute (one ExecuteRskill through the runner,
//        safety kernel, HAL; the contract is checked by the server)
//   Lookup  QueryCapability(String query, String args_json)          -> String value_json (UNKNOWN on failure)
//     -> space_harness_msgs/QueryCapability on /space/capability/query
//   Lookup  LastCapabilityResult()                                   -> String {capability, success, failure_kind,
//                                                                       failure_reason, evidence}
// No mission logic: no orderings, retries or recoveries -- those belong in the PLEXIL plan library (the baseline's
// pre-engineered knowledge), never in the adapter.
//
// SKELETON (§21.5 start): builds and loads; per-capability typed Commands (e.g. NavigateToPose(Real x, Real y,
// Real yaw)) and the plan library are the next step.

#include "AdapterConfiguration.hh"
#include "AdapterExecInterface.hh"
#include "AdapterFactory.hh"
#include "Command.hh"
#include "CommandHandle.hh"
#include "InterfaceAdapter.hh"
#include "LookupReceiver.hh"
#include "State.hh"
#include "Value.hh"

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
std::string json_escape(std::string const &s)
{
  std::string out;
  for (char c : s) {
    if (c == '"' || c == '\\') out.push_back('\\');
    out.push_back(c);
  }
  return out;
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
      [this](PLEXIL::Command *cmd, PLEXIL::AdapterExecInterface *intf) { executeCapability(cmd, intf); });
    config->registerLookupHandlerFunction(
      "QueryCapability",
      [this](PLEXIL::State const &state, PLEXIL::LookupReceiver *rcvr) { queryCapability(state, rcvr); });
    config->registerLookupHandlerFunction(
      "LastCapabilityResult",
      [this](PLEXIL::State const &, PLEXIL::LookupReceiver *rcvr) {
        std::lock_guard<std::mutex> lock(mutex_);
        rcvr->update(last_result_);
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
  void executeCapability(PLEXIL::Command *cmd, PLEXIL::AdapterExecInterface *intf)
  {
    std::vector<PLEXIL::Value> const &args = cmd->getArgValues();
    std::string capability, args_json = "{}";
    if (args.size() < 1 || !args[0].getValue(capability) || (args.size() > 1 && !args[1].getValue(args_json))) {
      intf->handleCommandAck(cmd, PLEXIL::COMMAND_FAILED);
      intf->notifyOfExternalEvent();
      return;
    }
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
      }
      intf->handleCommandReturn(cmd, PLEXIL::Value(static_cast<bool>(r.success)));
      intf->handleCommandAck(cmd, r.success ? PLEXIL::COMMAND_SUCCESS : PLEXIL::COMMAND_FAILED);
      intf->notifyOfExternalEvent();
    };
    execute_->async_send_goal(goal, opts);
  }

  void queryCapability(PLEXIL::State const &state, PLEXIL::LookupReceiver *rcvr)
  {
    std::string query, args_json = "{}";
    if (state.parameters().size() < 1 || !state.parameter(0).getValue(query) ||
        (state.parameters().size() > 1 && !state.parameter(1).getValue(args_json))) {
      rcvr->setUnknown();
      return;
    }
    auto req = std::make_shared<QueryCapability::Request>();
    req->query = query;
    req->args_json = args_json;
    auto future = query_->async_send_request(req);
    if (future.wait_for(std::chrono::seconds(5)) != std::future_status::ready || !future.get()->success) {
      rcvr->setUnknown();
      return;
    }
    rcvr->update(future.get()->value_json);
  }

  rclcpp::Node::SharedPtr node_;
  rclcpp_action::Client<ExecuteCapability>::SharedPtr execute_;
  rclcpp::Client<QueryCapability>::SharedPtr query_;
  std::unique_ptr<rclcpp::executors::MultiThreadedExecutor> executor_;  // after rclcpp::init
  std::thread spinner_;
  std::mutex mutex_;
  std::string last_result_ = "{}";
};

extern "C" {
void initCapabilityAdapter()
{
  REGISTER_ADAPTER(CapabilityAdapter, "CapabilityAdapter");
}
}
