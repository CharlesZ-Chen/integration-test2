import sys, os, shutil

import inv_check
import insert_jaif
import ontology_to_daikon
import pa2checker

import backend
import common

def run_pa2checker(annotations):
  pa2checker.revert_checker_source()

  for annotation, classes in annotations.iteritems():
    pa2checker.create_type_annotation(annotation)
    pa2checker.update_ontology_utils(annotation, classes)
  pa2checker.recompile_checker_framework()

def run_inference(project):
  common.setup_checker_framework_env()

  classpath = os.path.join(os.environ['JSR308'], 'generic-type-inference-solver', 'bin')
  if os.environ.get('CLASSPATH'):
    os.environ['CLASSPATH'] += ':' + classpath
  else:
    os.environ['CLASSPATH'] = classpath

  project_dir = common.get_project_dir(project)
  annotation_dir = os.path.join(project_dir, common.DLJC_OUTPUT_DIR, 'annotations')

  if os.path.isdir(annotation_dir):
    shutil.rmtree(annotation_dir)

  with common.cd(project_dir):
    common.clean_project(project)
    common.run_dljc(project,
                    ['inference'],
                    ['--solverArgs=backEndType=maxsatbackend.MaxSat',
                     '--checker', 'ontology.OntologyChecker',
                     '--solver', 'constraintsolver.ConstraintSolver',
                     '-m', 'ROUNDTRIP',
                     '-afud', annotation_dir])


def find_methods_with_signature(corpus, return_annotation, param_annotation_list):
  """ Finds all methods the corpus that have an annotation 'return_annotation' on the
  return value and the parameters annotated with 'param_annotation_list'
  OUTPUT: List of tuples (project, package, class, method)
  """
  good_methods = []

  for project in corpus:
    project_dir = common.get_project_dir(project)
    jaif_file = os.path.join(project_dir, "default.jaif")

    has_param = False
    has_ret = False
    current_package = ""
    current_class = ""
    current_method = ""
    with open(jaif_file, 'r') as f:
      for line in f.readlines():
        if line.startswith("package "):
          current_package = line[len("package "):line.find(":")]
        if line.startswith("class "):
          current_class = line[len("class "):line.find(":")]
        if line.startswith("method "):
          current_method = line[len("method "):line.find(":")]
          has_param = False
          has_ret = False

        if param_annotation_list!=None:
          if line.startswith("insert-annotation Method.parameter"):
            s = line[len("insert-annotation Method.parameter "):]
            param_idx = int(s[:s.find(",")])
            if len(param_annotation_list) > param_idx and param_annotation_list[param_idx] in line:
              has_param = True
            elif len(param_annotation_list) <= param_idx:
              has_param = False
        else:
          hase_param = True
        if return_annotation != None:
          if line.startswith("insert-annotation Method.type") and return_annotation in line:
            has_ret = True
        else:
          has_ret = True
        if has_param==True and has_ret==True:
          good_methods += [(project, current_package, current_class, current_method)]
          print ("Relevant Method: {}.{}".format(current_class,current_method))
          has_param = False
          has_ret = False
  return good_methods


def main(corpus, annotations, limit=3):
  """ SUMMARY: use case of the user-driven functionality of PASCALI.
  Scenario: User provides the concept of Sequence and the equivalent Java
  types, and the concept of sorted sequence and the relevant type invariant.
  Goal: learn how to get from Sequence -> Sorted Sequence.
  """

  """
  INPUT: annotations, dictionary mapping string -> list of strings
  OUTPUT: recompiles generic-inference-solver with new annotations"""

  run_pa2checker(annotations)

  """ Look for new mapping from 'ontology concepts'->'java type' and run
  checker framework. Should be implemented in type_inference
  Mapping example:
    Sequence -> java.lang.Array, java.util.List, LinkedHashSet, etc.

  INPUT: corpus, file containing set of concept->java_type mapping
  OUTPUT: Set of jaif files that are merged into the classes. The jaif files are
          stored as default.jaif in each project's directory.
  BODY: This also triggers back-end labeled graph generation.
  """

  for project in corpus:
    run_inference(project)

  """ Missing step: interact with PA to add a definition of Sorted Sequence
  which is a specialization of Sequence that has a sortedness invariants.
  The sortedness invariant gets turned into a Daikon template
  INPUT: user interaction
  OUTPUT: type_annotation and type_invariant (for sorted sequence)

  """

  ordering_operator = "<="

  ontology_invariant_file = "TODO_from_Howie.txt"
  with open(ontology_invariant_file, 'w') as f:
    f.write(ordering_operator)

  invariant_name = "TODO_sorted_sequence"

  daikon_pattern_java_file = ontology_to_daikon.create_daikon_invariant(ontology_invariant_file, invariant_name)


  """ Find all methods that have one input parameter annotated as Sequence and return a variable also
  annotated as Sequence.
  INPUT: The corpus and the desired annotations on the method signature
  OUTPUT: List of methods that have the desired signature.
  NOTE: This is a stub and will be implemented as LB query in the future.
  """
  sig_methods = find_methods_with_signature(corpus, "@ontology.qual.Sequence", ["@ontology.qual.Sequence"])
  print ("\n   ************")
  print ("The following corpus methods have the signature Sequence->Sequence {}:")
  for (project, package, clazz, method) in sig_methods:
    print("{}:\t{}.{}.{}".format(project, package, clazz, method))
  print ("\n   ************")


  """ Search for methods that have a return type annotated with Sequence
  and for which we can establish a sortedness invariant (may done by LB).

  INPUT: dtrace file of project
         daikon_pattern_java_file that we want to check on the dtrace file.

  OUTPUT: list of ppt names that establish the invariant. Here a ppt
  is a Daikon program point, s.a. test01.TestClass01.sort(int[]):::EXIT

  Note: this step translate the type_invariant into a Daikon
  template (which is a Java file).
  """

  pattern_class_name = invariant_name
  pattern_class_dir = os.path.join(common.WORKING_DIR, "invClass")
  if os.path.isdir(pattern_class_dir):
    shutil.rmtree(pattern_class_dir)
  os.mkdir(pattern_class_dir)

  cmd = ["javac", "-g", "-classpath", common.get_jar('daikon.jar'),
         daikon_pattern_java_file, "-d", pattern_class_dir]
  common.run_cmd(cmd)

  list_of_methods = []
  for project in corpus:
    dtrace_file = backend.get_dtrace_file_for_project(project)
    if not dtrace_file:
      print ("Ignoring folder {} because it does not contain dtrace file".format(project))
      continue
    ppt_names = inv_check.find_ppts_that_establish_inv(dtrace_file, pattern_class_dir, pattern_class_name)
    methods = set()
    for ppt in ppt_names:
      method_name = ppt[:ppt.find(':::EXIT')]
      methods.add(method_name)
    list_of_methods +=[(project, methods)]

  print ("\n   ************")
  print ("The following corpus methods return a sequence sorted by {}:".format(ordering_operator))
  for project, methods in list_of_methods:
    if len(methods)>0:
      print (project)
      for m in methods:
        print("\t{}".format(m))
  print ("\n   ************")

  shutil.rmtree(pattern_class_dir)

  """ Expansion of dynamic analysis results ....
  Find a list of similar methods that are similar to the ones found above (list_of_methods).
  INPUT: list_of_methods, corpus with labeled graphs generated, threshold value for similarity,
  OUTPUT: superset_list_of_methods
  """

  # WENCHAO
  print("Expanding the dynamic analysis results using graph-based similarity:")
  union_set = set()
  for project, methods in list_of_methods:
    # map Daikon output on sort method to method signature in methods.txt in generated graphs
    for m in methods:
      method_name = common.get_method_from_daikon_out(m)
      #kernel_file = common.get_kernel_path(project)
      method_file = common.get_method_path(project)
      dot_name = common.find_dot_name(method_name, method_file)
      if dot_name:
        # find the right dot file for each method
        dot_file = common.get_dot_path(project, dot_name)
        # find all graphs that are similar to it using WL based on some threshold
        sys.path.append(os.path.join(common.WORKING_DIR, 'simprog'))
        from similarity import Similarity
        sim = Similarity()
        sim.read_graph_kernels(os.path.join(common.WORKING_DIR, "corpus_kernel.txt"))
        top_k = 3
        iter_num = 3
        result_program_list_with_score = sim.find_top_k_similar_graphs(dot_file, 'g', top_k, iter_num)
        print(project+":")
        print(result_program_list_with_score)
        result_set = set([x[0] for x in result_program_list_with_score])
        # take the union of all these graphs
        union_set = union_set | result_set
  print("Expanded set:")
  print([x.split('/')[-4] for x in union_set])

  # return this set as a list of (project, method)
  fo = open("methods.txt", "w")
  expanded_list = []
  for dot_path in union_set:
    method_summary = common.get_method_summary_from_dot_path(dot_path)
    fo.write(method_summary)
    fo.write("\n")
  fo.close()

  """ Update the type annotations for the expanded dynamic analysis results.
  INPUT: superset_list_of_methods, annotation to be added
  OUTPUT: nothing
  EFFECT: updates the type annotations of the methods in superset_list_of_methods.
  This requires some additional checks to make sure that the methods actually
  perform some kind of sorting. Note that we do it on the superset because the original
  list_of_methods might miss many implementations because fuzz testing could not
  reach them.
  """
  for class_file in []: # MARTIN
    generated_jaif_file = "TODO"
    insert_jaif.merge_jaif_into_class(class_file, generated_jaif_file)


  """ Ordering of expanded dynamic analysis results ....
  Find the k 'best' implementations in superset of list_of_methods
  INPUT: superset_list_of_methods, corpus, k
  OUTPUT: k_list_of_methods
  Note: similarity score is used. may consider using other scores; e.g., TODO:???
  """

  #TODO: create input file for huascar where each line is formatted like:
  # ../corpus/Sort05/src/Sort05.java::sort(int[]):int[]

  ordering_dir = os.path.join(common.WORKING_DIR, "ordering_results/")

  methods_file = os.path.join(common.WORKING_DIR, 'methods.txt')
  with common.cd(ordering_dir):
    #TODO generate a proper relevant methods file.
    cmd = ["./run.sh",
           "-k", "{}".format(limit),
           "-t", "typicality",
           "-f", methods_file]
    common.run_cmd(cmd, print_output=True)

  """
  Close the loop and add the best implementation found in the previous
  step back to the ontology.
  INPUT: k_list_of_methods
  OUTPUT: patch file for the ontology. Worst case: just add the 'best' implementation
  found in the corpus as a blob to the ontology. Best case: generate an equivalent
  flow-graph in the ontology.
  """
  #print "TODO" # ALL



# if not os.path.isfile(daikon_jar):
#   print "Downloading dependencies"
#   cmd = ["./fetch_dependencies.sh"]
#   run_command(cmd)
#   print "Done."

if __name__ == '__main__':
  corpus = common.get_project_list()
  annotations = { "Sequence": ['java.util.List', 'java.util.LinkedHashSet'] }
  top_k = 3 
  if len(sys.argv)>1:
    annotations_file = sys.argv[1]
    if len(sys.argv)>2:
      top_k = sys.argv[2]
    with open(annotations_file, 'r') as f:
      annotations.clear()
      for line in f.readlines():
        pair = [x.strip() for x in line.split(',')]
        if len(pair)!=2:
          print ("Ignoring {}".format(line))
          continue;
        if pair[0] not in annotations:
          annotations[pair[0]] = []
        annotations[pair[0]] += [pair[1]]
    print (annotations)

  main(corpus, annotations, limit=top_k)
