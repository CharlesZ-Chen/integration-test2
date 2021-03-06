import os, sys
import common
import fetch_corpus

def run_petablox(project):
  with common.cd(common.get_project_dir(project)):
    petablox_cmd = ['java',
                    '-cp', common.get_jar('petablox.jar'),
                    '-Dpetablox.reflect.kind=none',
                    '-Dpetablox.run.analyses=cipa-0cfa-dlog',
                    'petablox.project.Boot']
    common.run_cmd(petablox_cmd)

def add_project_to_corpus(project):
  print "STARTED CLEANING PROJECT"
  common.clean_project(project)
  print "FINISHED CLEANING PROJECT"

  """Run dljc
  Run Randoop to generate test sources
  Compile test sources
  Run daikon.Chicory on tests to create dtrace file
  Precompute graph kernels that are independent of ontology stuff
  """
  #, 'dyntrace'
  common.run_dljc(project,
                  ['graphtool'],
                  ['--graph-jar', common.get_jar('prog2dfg.jar'),
                   '--dyntrace-libs', common.LIBS_DIR],
                   timelimit=300.0)

  """ run petablox """
  #run_petablox(project_dir)

  """ run graph kernel computation """
  project_dir = common.get_project_dir(project)
  kernel_file_path = common.get_kernel_path(project)

  graph_kernel_cmd = ['python',
                      common.get_simprog('precompute_kernel.py'),
                      project_dir,
                      kernel_file_path
                      ]
  common.run_cmd(graph_kernel_cmd)
  print 'Generated kernel file for {0}.'.format(project)
  return kernel_file_path

def update_corpus_project(project):
  """ This is triggered when new type annotations are being added either by
  checker_framework or when the frontend has discovered a set of methods that
  establish certain invariants."""

  """ Recompute dot files """  #Martin S
  print "TODO"

  """ Recompute various kernels """  #Wenchao
  print "TODO"


  """ Update petablox """
  print "TODO"


def find_methods_with_property(property):
  """ TODO we need to have sth to find all methods that take a sequence as input
  and return a sequence. Should be done by LB but can be hardcoded by Tim or Martin."""
  pass


def get_dtrace_file_for_project(project):
  if project == "TODO":
    return os.path.join(common.WORKING_DIR, 'inv_check/test.dtrace.gz')

  dtrace_path = os.path.join(common.CORPUS_DIR,
                             project,
                             common.DLJC_OUTPUT_DIR,
                             'RegressionTestDriver.dtrace.gz')
  if os.path.exists(dtrace_path):
    return dtrace_path
  else:
    return None

def main():
  fetch_corpus.fetch_corpus()

  with open("corpus_kernel.txt", "w") as kf:
    for project in common.get_project_list():
      try:
        print "Analyzing {}".format(project)

        project_kernel_file = add_project_to_corpus(project)
        with open(project_kernel_file, "r") as fi:
          kf.write(fi.read())

#        dtrace = get_dtrace_file_for_project(project)
#        if dtrace:
#          print "Generated {}".format(dtrace)
      except Exception as e:
        print "Error analyzing {}: {}".format(project, e)

if __name__ == '__main__':
  main()
  os._exit(0)
