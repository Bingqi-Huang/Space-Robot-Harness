// PLEXIL Release 6 interface adapter that links the EUROPA host (baselines/europa/host.py) to the exec -- the
// EUROPA->PLEXIL bridge's transport (execution_plan §11.2 "PLEXIL execution bridge"). No mission logic: the host
// decides what runs next, the dispatch plan (plans/ActivityDispatch.ple) runs it through the common capability
// adapter, this adapter only carries the two ends.
//
//   Command NextActivity()        -> String  the next activity's capability name; "" = the host has ended the run
//   Lookup  ActivityArgs()        -> String  that activity's arguments, a JSON object
//   Command ReportResult(String)  -> Boolean the capability result JSON handed back to the host
//
// Transport: one TCP connection to the host (<Adapter AdapterType="HostLink" port="..."/>), frames of
// "<byte length>\n<payload>". NEXT is answered by two frames (capability, args_json); RESULT + payload by "OK".
// Commands block on the host (it replans between activities), so each runs on its own thread.

#include "AdapterConfiguration.hh"
#include "AdapterExecInterface.hh"
#include "AdapterFactory.hh"
#include "Command.hh"
#include "InterfaceAdapter.hh"
#include "LookupReceiver.hh"
#include "State.hh"
#include "Value.hh"

#include "pugixml.hpp"

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <mutex>
#include <string>
#include <thread>

class HostLinkAdapter : public PLEXIL::InterfaceAdapter
{
public:
  HostLinkAdapter(PLEXIL::AdapterExecInterface &intf, PLEXIL::AdapterConf *conf)
  : PLEXIL::InterfaceAdapter(intf, conf)
  {
  }

  bool initialize(PLEXIL::AdapterConfiguration *config) override
  {
    port_ = getXml().attribute("port").as_int(47810);
    config->registerCommandHandlerFunction(
      "NextActivity", [this](PLEXIL::Command *cmd, PLEXIL::AdapterExecInterface *intf) {
        std::thread([this, cmd, intf] {
          std::string capability;
          {
            std::lock_guard<std::mutex> lock(mutex_);
            send("NEXT");
            capability = recv();
            args_ = recv();
          }
          intf->handleCommandReturn(cmd, PLEXIL::Value(capability));
          intf->handleCommandAck(cmd, PLEXIL::COMMAND_SUCCESS);
          intf->notifyOfExternalEvent();
        }).detach();
      });
    config->registerCommandHandlerFunction(
      "ReportResult", [this](PLEXIL::Command *cmd, PLEXIL::AdapterExecInterface *intf) {
        std::string result;
        cmd->getArgValues()[0].getValue(result);
        std::thread([this, cmd, intf, result] {
          bool ok;
          {
            std::lock_guard<std::mutex> lock(mutex_);
            send("RESULT");
            send(result);
            ok = recv() == "OK";
          }
          intf->handleCommandReturn(cmd, PLEXIL::Value(ok));
          intf->handleCommandAck(cmd, ok ? PLEXIL::COMMAND_SUCCESS : PLEXIL::COMMAND_FAILED);
          intf->notifyOfExternalEvent();
        }).detach();
      });
    config->registerLookupHandlerFunction(
      "ActivityArgs", [this](PLEXIL::State const &, PLEXIL::LookupReceiver *rcvr) {
        std::lock_guard<std::mutex> lock(mutex_);
        rcvr->update(args_);
      });
    return true;
  }

  bool start() override
  {
    fd_ = socket(AF_INET, SOCK_STREAM, 0);
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port_);
    inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);
    return connect(fd_, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) == 0;
  }

  void stop() override { close(fd_); }

private:
  void send(std::string const &payload)
  {
    std::string frame = std::to_string(payload.size()) + "\n" + payload;
    for (size_t off = 0; off < frame.size();) off += ::send(fd_, frame.data() + off, frame.size() - off, 0);
  }

  std::string recv()
  {
    std::string len;
    char c;
    while (::recv(fd_, &c, 1, 0) == 1 && c != '\n') len.push_back(c);
    std::string payload(std::stoul(len), '\0');
    for (size_t off = 0; off < payload.size();) off += ::recv(fd_, &payload[off], payload.size() - off, 0);
    return payload;
  }

  int port_ = 47810;
  int fd_ = -1;
  std::mutex mutex_;
  std::string args_ = "{}";
};

extern "C" {
void initHostLink()
{
  REGISTER_ADAPTER(HostLinkAdapter, "HostLink");
}
}
