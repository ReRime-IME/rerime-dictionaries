// Separate executable: no deploy/prebuild/maintenance function is called here.
#include <rime_api.h>
#include <filesystem>
#include <iostream>
#include <string>
extern void rime_require_module_core();
extern void rime_require_module_dict();
extern void rime_require_module_gears();
namespace rime { extern void rime_require_module_default(); }
int main(int argc, char** argv) {
  if (argc != 6) return 2;
  std::string root=argv[1], schema=argv[2], input=argv[3], expected=argv[4], build=root+"/build";
  if (!std::filesystem::is_regular_file(build+"/"+schema+".table.bin")) return 3;
  rime_require_module_core(); rime_require_module_dict(); rime_require_module_gears(); rime::rime_require_module_default();
  auto api=rime_get_api(); if (std::string(api->get_version())!="1.16.1") return 4;
  RimeTraits traits={}; RIME_STRUCT_INIT(RimeTraits, traits);
  traits.user_data_dir=root.c_str(); traits.prebuilt_data_dir=build.c_str(); traits.staging_dir=build.c_str();
  traits.app_name="rime.rerime_public_consumer";
  api->setup(&traits); api->initialize(&traits);
  auto session=api->create_session();
  if (!session || !api->select_schema(session,schema.c_str())) { api->finalize(); return 5; }
  api->set_option(session,"traditionalization",std::string(argv[5])=="traditional");
  for (unsigned char key:input) api->process_key(session,key,0);
  bool selected=false;
  for (int page=0;page<20&&!selected;page++) {
    RimeContext context={}; RIME_STRUCT_INIT(RimeContext,context);
    if (!api->get_context(session,&context)) break;
    int match=-1;
    for (int i=0;i<context.menu.num_candidates;i++) if (expected==context.menu.candidates[i].text) { match=i; break; }
    bool last=context.menu.is_last_page; api->free_context(&context);
    if (match>=0) selected=api->select_candidate_on_current_page(session,match);
    else if (last) break;
    else api->change_page(session,False);
  }
  RimeCommit commit={}; RIME_STRUCT_INIT(RimeCommit,commit); bool equal=false;
  if (api->get_commit(session,&commit)) { equal=commit.text&&expected==commit.text; api->free_commit(&commit); }
  api->destroy_session(session); api->finalize();
  std::cout << "candidate_selected="<<selected<<" commit_matched="<<equal<<" deployment_calls=0"<<std::endl;
  return selected&&equal ? 0 : 6;
}
