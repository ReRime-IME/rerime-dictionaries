// Separate executable: no deploy/prebuild/maintenance function is called here.
// Usage: RimeConsumer root schema input expected mode [keys|set_input] [expected-comment|-]
// expected "*" accepts the first candidate of a non-empty menu.
#include <rime_api.h>
#include <filesystem>
#include <iostream>
#include <string>
#include <sys/resource.h>
extern void rime_require_module_core();
extern void rime_require_module_dict();
extern void rime_require_module_gears();
namespace rime { extern void rime_require_module_default(); }
int main(int argc, char** argv) {
  if (argc != 6 && argc != 8) return 2;
  std::string root=argv[1], schema=argv[2], input=argv[3], expected=argv[4], build=root+"/build";
  std::string feed=argc==8?argv[6]:"keys", comment=argc==8?argv[7]:"-";
  if (feed!="keys" && feed!="set_input") return 2;
  // The nine-key schema mounts the shared wanxiang table under its own prism.
  std::string dictionary=schema=="wanxiang_t9"?"wanxiang":schema;
  if (!std::filesystem::is_regular_file(build+"/"+dictionary+".table.bin")) return 3;
  if (!std::filesystem::is_regular_file(build+"/"+schema+".prism.bin")) return 3;
  rime_require_module_core(); rime_require_module_dict(); rime_require_module_gears(); rime::rime_require_module_default();
  auto api=rime_get_api(); if (std::string(api->get_version())!="1.16.1") return 4;
  RimeTraits traits={}; RIME_STRUCT_INIT(RimeTraits, traits);
  traits.user_data_dir=root.c_str(); traits.prebuilt_data_dir=build.c_str(); traits.staging_dir=build.c_str();
  traits.app_name="rime.rerime_public_consumer";
  api->setup(&traits); api->initialize(&traits);
  auto session=api->create_session();
  if (!session || !api->select_schema(session,schema.c_str())) { api->finalize(); return 5; }
  api->set_option(session,"traditionalization",std::string(argv[5])=="traditional");
  if (feed=="set_input") { if (!api->set_input(session,input.c_str())) { api->destroy_session(session); api->finalize(); return 5; } }
  else for (unsigned char key:input) api->process_key(session,key,0);
  bool selected=false, any=expected=="*"; std::string found_comment, found_text; int candidates=0;
  for (int page=0;page<20&&!selected;page++) {
    RimeContext context={}; RIME_STRUCT_INIT(RimeContext,context);
    if (!api->get_context(session,&context)) break;
    if (page==0) candidates=context.menu.num_candidates;
    int match=-1;
    for (int i=0;i<context.menu.num_candidates;i++) if (any || expected==context.menu.candidates[i].text) { match=i; break; }
    if (match>=0) {
      found_text=context.menu.candidates[match].text;
      if (context.menu.candidates[match].comment) found_comment=context.menu.candidates[match].comment;
    }
    bool last=context.menu.is_last_page; api->free_context(&context);
    if (match>=0) selected=api->select_candidate_on_current_page(session,match);
    else if (last) break;
    else api->change_page(session,False);
  }
  RimeCommit commit={}; RIME_STRUCT_INIT(RimeCommit,commit); bool equal=false;
  if (api->get_commit(session,&commit)) { equal=commit.text&&(any?found_text==commit.text:expected==commit.text); api->free_commit(&commit); }
  api->destroy_session(session); api->finalize();
  bool comment_matched=comment=="-"||comment==found_comment;
  rusage usage{}; long peak=getrusage(RUSAGE_SELF,&usage)==0?usage.ru_maxrss:0;
  std::cout << "candidate_selected="<<selected<<" commit_matched="<<equal<<" first_page_candidates="<<candidates
            << " comment=\""<<found_comment<<"\" comment_matched="<<comment_matched
            << " peak_resident_bytes="<<peak<<" deployment_calls=0"<<std::endl;
  return selected&&equal&&comment_matched ? 0 : 6;
}
