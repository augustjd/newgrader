#!/usr/bin/env python

import datetime
import os
import sys
import glob

from contextlib import contextmanager
from distutils.dir_util import copy_tree, remove_tree
from uuid import uuid4
from models import (Assignment, 
                    Submission, 
                    Student, 
                    Session, 
                    TestSceneRun,
                    CREATIVE_SCENE)

# the width of the terminal output. things are left-padded
# to hit this target width.
MAIN_WIDTH = 72

VALID_SCENE_EXTENSIONS = ['.xml']
VALID_MOVIE_EXTENSIONS = ['.mpeg', '.mpg', '.mov', '.mkv', '.avi', '.mp4']

def find(iterable):
    try:
        result = iterable.next()
    except StopIteration:
        result = None

    return result

@contextmanager
def chdir(d):
    old_cwd = os.getcwd()
    os.chdir(d)
    try:
        yield
    finally:
        os.chdir(old_cwd)

SUBMISSIONS_DIRECTORY = "./submissions"

def bold(s):
    return "\033[1m{0}\033[0m".format(s)

def green(s):
    return "\033[32m{0}\033[0m".format(s)

def blue(s):
    return "\033[34m{0}\033[0m".format(s)

def red(s):
    return "\033[31m{0}\033[0m".format(s)

def get_current_assignments(session):
    return Assignment.get_current_assignments(session)

def fatal(msg):
    print_fatal(msg)
    sys.exit(1)

def fatal_cancel(submission_folder, msg):
    print_fatal(msg)
    cancel_submission(submission_folder)
    sys.exit(0)

def print_fatal(msg, spaces=True):
    if spaces:
        print("")
    print(red(bold("FATAL ERROR: ") + msg + " Exiting."))
    if spaces:
        print("")

def check_original_folder_for_fosssim(original_folder):
    '''
    Ensures that the directory about to be submitted is formatted as expected.
    '''
    if not os.path.exists(original_folder):
        fatal("Folder '{}' does not exist.".format(original_folder))

    if not os.path.exists(os.path.join(original_folder, 'FOSSSim')):
        fatal("Couldn't find 'FOSSSim' directory in the top level of the submission folder.")

    if not os.path.exists(os.path.join(original_folder, 'Creative')):
        fatal("Couldn't find 'Creative' directory in your submitted directory.")

def get_submission_folder_path(assignment, uni):
    if not os.path.exists(SUBMISSIONS_DIRECTORY):
        os.mkdir(SUBMISSIONS_DIRECTORY)

    parent_dir = os.path.join(SUBMISSIONS_DIRECTORY, "t{}m{}".format(assignment.theme, assignment.milestone))

    if not os.path.exists(parent_dir):
        os.mkdir(parent_dir)

    return os.path.join(parent_dir, "{}-{}-{}/".format(uni, assignment.name(), uuid4()))

def prepare_submission_folder(original_folder, submission_folder, assignment):
    '''
    Copies all the files into the submission folder, to prepare for
    compilation and testing.
    '''
    if not os.path.exists(assignment.template_path):
        fatal("Couldn't find assignment starter code at '{}'.".format(assignment.template_path))

    copy_tree(assignment.template_path, submission_folder)
    os.system("chmod -R 777 " + submission_folder)
    copy_tree(os.path.join(original_folder, 'FOSSSim'), 
              os.path.join(submission_folder, 'FOSSSim'))

    copy_tree(os.path.join(original_folder, 'Creative'), 
              os.path.join(submission_folder, 'Creative'))

def compile_submission(submission_folder):
    build_folder = os.path.join(submission_folder, 'build/')
    if not os.path.exists(build_folder):
        os.mkdir(build_folder)
        if not os.path.exists(build_folder):
            fatal("Build directory was not correctly copied into the submission folder.")

    with chdir(build_folder):
        os.system('cmake -DCMAKE_BUILD_TYPE=Release ..')
        compilation_result = os.system('make -j')

        if compilation_result > 0:
            fatal_cancel(submission_folder, "Compilation failed.")

        expected_binary_path = os.path.abspath(os.path.join("./FOSSSim", "FOSSSim"))
        if not os.path.isfile(expected_binary_path):
            fatal_cancel(submission_folder, "Binary executable wasn't found in '{0}'.".format(expected_binary_path))

    return expected_binary_path
def shorten_test_path(path):
    return '/'.join(path.split('/')[-3:])

def print_test(path):
    path = shorten_test_path(path)
    s = "    {0}".format(blue(path))

    # add some padding
    s += (' ' * (MAIN_WIDTH - len(path) - 10))

    sys.stdout.write(s)

def print_result(result):
    if result is True:
        sys.stdout.write(bold(green("[ OK ]\n")))
    elif result is False:
        sys.stdout.write(bold(  red("[FAIL]\n")))
    elif result is None:
        sys.stdout.write(bold(      "[N/A ]\n"))

def run_tests(submission_executable, assignment, hashstr):
    tests = assignment.tests()
    runs = []

    print("")
    print("=" * MAIN_WIDTH)
    print("  Test Results:")
    print("=" * MAIN_WIDTH)
    print("")

    for t in tests:
        print_test(t.filepath)

        result = t.run(submission_executable, assignment.oracle_path, hashstr)

        if result is None:
            print("Couldn't determine result of test '{0}'.".format(t.filepath.split('/')[-1]))
        else:
            print_result(result)
            runs.append(TestSceneRun(path=t.filepath, success=result))

    return runs

def print_test_summary(results, last_submission=None):
    success = len([r for r in results if r.success])
    print("")
    print("=" * MAIN_WIDTH)
    print("")

    def print_passed(passed_runs, total_runs):
        if (total_runs == 0): 
            percentage = 100.0
        else:
            percentage = 100 * round(float(passed_runs) / total_runs, 3)

        print("Passed {} / {} tests for a grade of {}%.".format(
            bold(green(str(passed_runs))), 
            bold(str(total_runs)),
            bold(blue(str(percentage)))))

    if len(results) > 0:
        print_passed(success, len(results))

    if last_submission is not None:
        print("")
        print("Compare that to your last submission:")
        print_passed(len(last_submission.passed_runs()),
                     len(last_submission.test_runs))

    print("")

def ask_user_for_assignment(assignments=[]):
    print("Available assignments:")
    for a in assignments:
        print("\t{}".format(bold(green(a.name()))))

    response = None
    while response < 0:
        try:
            response_str = raw_input("Name of assignment you would like to submit: ")
        except EOFError:
            print("")
            sys.exit(1)

        response = find(a for a in assignments if a.name() == response_str)
        if response is None:
            print("No assignment titled {} was found.".format(response_str))

    print("You've selected to submit {}.".format(bold(green(response.name()))))

    return response

def user_wants_to_submit():
    return "y" in raw_input("Submit [y/n]: ")


def get_valid(msg, parser=lambda s: int(s)):
    result = None
    while result is None:
        try:
            result_str = raw_input(msg)
            result = parser(result_str)
        except ValueError:
            print("{} is not a valid response.".format(result_str))

    return result

def get_comments():
    print("Any other comments (hit enter twice when you're done):")
    result = ""
    while True:
        new_line = raw_input("")
        if len(new_line) == 0:
            break

        result += " " + new_line

    return result

def gather_question_responses(submission):
    '''
    Gets a fun, frustration, and comment rating for this submission.
    '''
    def validate_rating(s):
        print("Validating " + s)
        i = int(s)
        if i not in range(1,6):
            raise ValueError()
        return i

    submission.difficulty_rating  = get_valid("How difficult was this assignment [1-5]? ", 
                                              validate_rating)
    submission.fun_rating         = get_valid("How fun was this assignment [1-5]? ", 
                                              validate_rating)
    submission.frustration_rating = get_valid("How frustrating was this assignment [1-5]? ",
                                              validate_rating)

    submission.comments = get_comments()

def perform_submission(ses, student, test_results, submission_folder, assignment):
    submission = Submission(assignment=assignment, student=student)

    if assignment.deliverable == CREATIVE_SCENE:
        try:
            gather_question_responses(submission)
        except EOFError:
            cancel_submission(submission_folder)

    ses.add(submission)
    ses.commit()

    for t in test_results:
        t.submission_id = submission.id
        ses.add(t)

    ses.commit()

    print("")
    print(bold("Your submission is complete with ID {}!\n".format(blue(submission.id))) + 
          "Keep track of this ID. If something goes wrong \n" +
          "with your submission, inform your TA of this number.")

def locate_creative_files(student, assignment, submission_folder):
    match_str = "{uni}_t{theme}m{milestone}.*".format(
            uni=student.uni,
            theme=assignment.theme,
            milestone=assignment.milestone)

    movie_file = None
    scene_file = None

    with chdir(submission_folder):
        possible_files = glob.glob(os.path.join("./Creative/", match_str))
        for f in possible_files:
            basename = os.path.basename(f)
            rest, ext = os.path.splitext(f)
            if ext in VALID_MOVIE_EXTENSIONS:
                movie_file = basename
            elif ext in VALID_SCENE_EXTENSIONS:
                scene_file = basename

    if movie_file is None or scene_file is None:
        if movie_file is None:
            print_fatal("Failed to find a movie file in your Creative directory.", False)

        if scene_file is None:
            print_fatal("Failed to find a scene file in your Creative directory.", False)

        cancel_submission(submission_folder)
        sys.exit(1)
    else:
        print("")
        print("Identified Creative Scene video file: {}".format(bold(green(movie_file))))
        print("Identified Creative Scene scene file: {}".format(bold(green(scene_file))))
        print("")


def submit_assignment(ses, student, original_folder, submission_folder, assignment):
    prepare_submission_folder(original_folder, submission_folder, assignment)

    results = []
    if not assignment.is_creative_scene():
        submission_executable = compile_submission(submission_folder)

        try:
            results = run_tests(submission_executable, assignment, uuid4().hex)
        except:
            print_fatal("Python Error while running tests.")
            cancel_submission(submission_folder)
            raise

        last_submission = ses.query(Submission).filter(Submission.student == student)\
                                               .filter(Submission.assignment == assignment)\
                                               .order_by(Submission.submission_time.desc())\
                                               .first()
        print_test_summary(results, last_submission)
    else:
        locate_creative_files(student, assignment, submission_folder)

    if user_wants_to_submit():
        perform_submission(ses, student, results, submission_folder, assignment)
    else:
        cancel_submission(submission_folder)

def get_assignment(ses):
    assignments = get_current_assignments(ses)
    if len(assignments) == 0:
        print("No assignments are available to submit.")
        sys.exit(0)

    # Which open assignment does the user intend to submit?
    return ask_user_for_assignment(assignments)

def get_student_of_uni(ses, uni):
    student = ses.query(Student).filter(Student.uni == uni).first()

    if student is None:
        print("Creating student {}".format(uni))
        student = Student(uni)
        ses.add(student)
        try:
            ses.commit()
        except Exception:
            fatal("Failed to create new student with UNI {}.".format(uni))

    return student

def process_submission(uni, original_folder):
    '''
    The main function, that takes a student's UNI and a path to the submitted
    folder, and runs test scenes, calculates a grade, and adds rows to the
    database for this submission (unless the user cancels submission).
    '''
    ses = Session()

    student = get_student_of_uni(ses, uni)

    check_original_folder_for_fosssim(original_folder)

    assignment = get_assignment(ses)

    submission_folder = os.path.abspath(get_submission_folder_path(assignment, uni))

    submit_assignment(ses, student, original_folder, submission_folder, assignment)

def cancel_submission(submission_folder):
    remove_tree(submission_folder)
    print("Submission canceled.")


def main():
    process_submission(sys.argv[2], sys.argv[1])

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("{} <Submission Directory> <UNI>".format(sys.argv[0]))
        sys.exit(1)

    main()
