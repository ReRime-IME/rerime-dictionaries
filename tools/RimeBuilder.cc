// Public iOS build tool. No private ReRime bridge dependency.
#include <rime_api.h>
#include <filesystem>
#include <iostream>
#include <string>
#include <fstream>
#include <chrono>
#include <sys/resource.h>
extern void rime_require_module_core();
extern void rime_require_module_dict();
extern void rime_require_module_gears();
extern void rime_require_module_levers();
namespace rime { extern void rime_require_module_default(); extern void rime_require_module_deployer(); }
int main(int argc, char** argv) {
  if (argc != 2) return 2;
  const auto started = std::chrono::steady_clock::now();
  std::string root = argv[1], build = root + "/build", logs = root + "/build-logs";
  if (std::filesystem::exists(build)) return 3;
  std::filesystem::create_directory(build); std::filesystem::create_directory(logs);
  rime_require_module_core(); rime_require_module_dict(); rime_require_module_gears(); rime_require_module_levers();
  rime::rime_require_module_default(); rime::rime_require_module_deployer();
  auto api = rime_get_api();
  if (std::string(api->get_version()) != "1.16.1") return 4;
  RimeTraits traits = {}; RIME_STRUCT_INIT(RimeTraits, traits);
  traits.shared_data_dir = root.c_str(); traits.user_data_dir = root.c_str();
  traits.prebuilt_data_dir = build.c_str(); traits.staging_dir = build.c_str();
  traits.log_dir = logs.c_str(); traits.app_name = "rime.rerime_public_builder";
  api->setup(&traits); api->initialize(&traits); api->deployer_initialize(&traits);
  bool success = api->deploy(); api->join_maintenance_thread(); api->finalize();
  std::cout << "engine=1.16.1 deployment_calls=1 success=" << success << std::endl;
  rusage usage{};
  if (getrusage(RUSAGE_SELF, &usage) != 0 || usage.ru_maxrss <= 0) return 6;
  const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - started).count();
  std::ofstream metrics(root + "/builder-resources.json");
  metrics << "{\"elapsed_ms\":" << elapsed << ",\"peak_resident_bytes\":" << usage.ru_maxrss << "}\n";
  metrics.close();
  if (!metrics) return 6;
  return success ? 0 : 5;
}
