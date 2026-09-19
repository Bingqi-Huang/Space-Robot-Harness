// The EUROPA side of the EUROPA->PLEXIL baseline (execution_plan §11.2 steps 1, 3, 4): load an NDDL problem (model +
// current state as facts + mission goals as goal tokens) into a fresh Plan Database, run the configured solver, and
// print the plan's activity tokens as one JSON object on stdout:
//   {"solved": bool, "steps": n, "activities": [{"key", "type", "params": {..}, "start": [lb, ub], "end": [lb, ub],
//                                                "slaves": [{"timeline", "type", "params", "start"}]}]}
// Activities are the active, non-fact tokens whose type starts with <activity_prefix> (the class that owns the
// capability actions), ordered by earliest start. The host (host.py) owns the loop around this call.
//
//   europa_plan <problem.nddl> <PlannerConfig.xml> <horizon> <max_steps> <activity_prefix>

#include "PSEngine.hh"
#include "PSPlanDatabase.hh"
#include "PSSolvers.hh"
#include "PSVarValue.hh"
#include "NddlInterpreter.hh"

#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <vector>

using namespace EUROPA;

std::string json_str(std::string const &s)
{
  std::string out = "\"";
  for (char c : s) {
    if (c == '"' || c == '\\') out.push_back('\\');
    out.push_back(c);
  }
  return out + "\"";
}

std::string value_json(PSVariable *v)
{
  if (!v->isSingleton()) return json_str(v->toString());
  PSVarValue x = v->getSingletonValue();
  std::ostringstream s;
  switch (x.getType()) {
    case OBJECT: return json_str(x.asObject()->getEntityName());
    case STRING: return json_str(x.asString());
    case BOOLEAN: return x.asBoolean() ? "true" : "false";
    case INTEGER: s << x.asInt(); return s.str();
    default: s << x.asDouble(); return s.str();
  }
}

std::string bounds_json(PSVariable *v)
{
  std::ostringstream s;
  if (v->isSingleton()) s << "[" << v->getSingletonValue().asDouble() << ", " << v->getSingletonValue().asDouble() << "]";
  else s << "[" << v->getLowerBound() << ", " << v->getUpperBound() << "]";
  return s.str();
}

int main(int argc, char const **argv)
{
  std::string problem = argv[1], config = argv[2], prefix = argv[5];
  int horizon = std::atoi(argv[3]), max_steps = std::atoi(argv[4]);
  PSEngine *engine = PSEngine::makeInstance();
  engine->start();
  try {
    engine->executeScript("nddl", problem, true);
  } catch (PSLanguageExceptionList const &e) {  // a model or problem that does not parse: report it, no plan
    std::cerr << e << std::endl;
    std::cout << "{\"solved\": false, \"steps\": 0, \"activities\": [], \"error\": \"nddl\"}" << std::endl;
    return 1;
  }
  PSSolver *solver = engine->createSolver(config);
  solver->configure(0, horizon);
  bool solved = false;
  while (!solver->isExhausted() && !solver->isTimedOut() && solver->getStepCount() < max_steps) {
    solver->step();
    if (solver->isConstraintConsistent() && solver->getFlaws().size() == 0) {
      solved = true;
      break;
    }
  }
  std::vector<std::pair<double, std::string>> acts;
  PSList<PSToken *> tokens = engine->getTokens();
  for (int i = 0; solved && i < tokens.size(); ++i) {
    PSToken *t = tokens.get(i);
    if (t->isFact() || t->getTokenState() != ACTIVE || t->getFullTokenType().rfind(prefix, 0) != 0) continue;
    std::ostringstream s;
    s << "{\"key\": " << t->getEntityKey() << ", \"type\": " << json_str(t->getFullTokenType()) << ", \"params\": {";
    PSList<PSVariable *> params = t->getPredicateParameters();
    for (int j = 0; j < params.size(); ++j)
      s << (j ? ", " : "") << json_str(params.get(j)->getEntityName()) << ": " << value_json(params.get(j));
    s << "}, \"start\": " << bounds_json(t->getStart()) << ", \"end\": " << bounds_json(t->getEnd()) << ", \"slaves\": [";
    // the tokens the activity's rule put on timelines (conditions and effects); the host reads the post-state off them
    PSList<PSToken *> slaves = t->getSlaves();
    for (int j = 0; j < slaves.size(); ++j) {
      PSToken *sl = slaves.get(j);
      if (sl->getTokenState() == MERGED) sl = sl->getActive();  // a merged slave's values live on its active token
      s << (j ? ", " : "") << "{\"timeline\": " << json_str(sl->getOwner() ? sl->getOwner()->getEntityName() : "")
        << ", \"type\": " << json_str(sl->getFullTokenType()) << ", \"params\": {";
      PSList<PSVariable *> sp = sl->getPredicateParameters();
      for (int k = 0; k < sp.size(); ++k)
        s << (k ? ", " : "") << json_str(sp.get(k)->getEntityName()) << ": " << value_json(sp.get(k));
      s << "}, \"start\": " << bounds_json(sl->getStart()) << "}";
    }
    s << "]}";
    acts.emplace_back(t->getStart()->isSingleton() ? t->getStart()->getSingletonValue().asDouble()
                                                   : t->getStart()->getLowerBound(), s.str());
  }
  std::stable_sort(acts.begin(), acts.end(), [](auto const &a, auto const &b) { return a.first < b.first; });
  std::cout << "{\"solved\": " << (solved ? "true" : "false") << ", \"steps\": " << solver->getStepCount()
            << ", \"activities\": [";
  for (size_t i = 0; i < acts.size(); ++i) std::cout << (i ? ", " : "") << acts[i].second;
  std::cout << "]}" << std::endl;
  delete solver;
  delete engine;
  return 0;
}
