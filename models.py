#!/usr/bin/env python

import datetime
import os
import sys
from subprocess import Popen, PIPE, STDOUT

from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base

DATABASE_FILEPATH = "./testgrade.db"

TEST_EXTENSION = ".xml"

engine = create_engine('sqlite:///{0}'.format(DATABASE_FILEPATH))
Session = sessionmaker(bind=engine)

Base = declarative_base()

def bold(s):
    return "\033[1m{0}\033[0m".format(s)

class TestScene(object):
    def __init__(self, filepath, graded=True, hidden=False):
        self.filepath = filepath
        self.graded = graded
        self.hidden = hidden

    def run(self, submission_binary, oracle_binary, hashstr, output_file=None):
        if output_file is None:
            output_file = "./output_" + hashstr + ".bin"

        residual_file = "./residual.txt"

        # run the submission binary to generate the output file
        result_code = Popen([submission_binary, "-s", self.filepath, "-d", "0", "-o", output_file], stdout=PIPE, stderr=STDOUT).wait()
        if result_code != 0:
            sys.stdout.write(bold(      "[N/A ]\n"))
            print(("Student executable crashed (exit code {}).").format(result_code, submission_binary))
            return None

        if not os.path.isfile(output_file):
            sys.stdout.write(bold(      "[N/A ]\n"))
            print("Failed to generate output file '{}'.".format(output_file))
            return None

        if not os.path.isfile(oracle_binary):
            sys.stdout.write(bold(      "[N/A ]\n"))
            print("Failed to open oracle '{}'.".format(oracle_binary))
            return None

        # run the oracle to grade the output file
        out, err = Popen([oracle_binary, "-s", self.filepath, "-d", "0", "-i", output_file], stdout=PIPE).communicate()

        os.remove(output_file)
        os.remove(residual_file)

        if "Overall success: Passed" in out:
            return True
        elif "Overall success: Failed" in out:
            return False
        else:
            return None

class Student(Base):
    __tablename__ = "students"

    id  = Column(Integer, primary_key=True)
    uni = Column(String)

    submissions = relationship("Submission",  lazy='dynamic', backref="student")

    def __init__(self, uni):
        self.uni = uni

    def best_submission_on(self, assignment):
        return self.submissions.outerjoin(TestSceneRun)\
                        .filter(TestSceneRun.success == True)\
                        .all()

    def grade_on(self, assignment):
        submission =  self.submissions.filter(Submission.assignment == assignment)\
                                      .order_by(Submission.submission_time.desc())\
                                      .first()
        if submission is None:
            return 0.0
        else:
            return submission.grade()


CREATIVE_SCENE = 3 # deliverable 3 is the creative scene
class Assignment(Base):
    __tablename__ = "assignments"

    id  = Column(Integer, primary_key=True)

    theme       = Column(Integer)
    milestone   = Column(Integer)
    deliverable = Column(Integer)

    oracle_path = Column(String)
    
    # the path to the assignment directory
    template_path = Column(String)

    start_date = Column(DateTime)
    due_date = Column(DateTime)

    submissions = relationship("Submission", backref='assignment')
    directories = relationship("AssignmentAssetDirectory", backref='assignment')

    def __init__(self, **kwargs):
        self.set_dict(**kwargs)

    def set_dict(self, theme=None, milestone=None, deliverable=None,
            oracle_path=None, template_path=None, start_date=None,
            due_date=None, directories=None):
        self.tests = None

        self.theme = theme
        self.milestone = milestone
        self.deliverable = deliverable
        self.oracle_path = oracle_path
        self.template_path = template_path
        self.start_date = start_date
        self.due_date = due_date

        if directories is not None:
            pass

    def __json__(self):
        return {
            "id":self.id,
            "theme":self.theme,
            "milestone":self.milestone,
            "deliverable":self.deliverable,
            "oracle_path":self.oracle_path,
            "template_path":self.template_path,
            "start_date":self.start_date,
            "due_date":self.due_date,
            "asset_directories":[d.__json__() for d in self.directories]
        }


    @staticmethod
    def get_late_window():
        return datetime.timedelta(hours=10)

    @staticmethod
    def get_current_assignments(session=None):
        if session is None:
            session = Session()

        now = datetime.datetime.now()

        # duration of time after the official 'due date' during which time
        # you can still submit.
        late_window = Assignment.get_late_window()

        # due_date + late_window = absolute_deadline, so if
        # absolute_deadline      > now we're fine. i.e.,
        # due_date + late_window > now
        # due_date               > now - late_window

        return session.query(Assignment).filter(Assignment.due_date >= now - late_window)\
                                        .filter(Assignment.start_date <= now)\
                                        .all()


    def is_creative_scene(self):
        return self.deliverable == CREATIVE_SCENE

    def name(self):
        return "t{}m{}d{}".format(self.theme, self.milestone, self.deliverable)

    def __str__(self):
        return "<Assignment {} due on {}>:\n\t{}".format(self.name(),
                self.start_date,
                "\n\t".join(map(str, self.directories)))

    def graded_tests_count(self):
        return len(t for t in self.tests() if t.graded)

    def tests(self):
        tests = []

        for d in self.directories:
            tests += d.tests()

        return tests

class AssignmentAssetDirectory(Base):
    '''
    A directory of test assets (scene files) associated with an assignment.
    '''
    __tablename__ = "assignment_asset_directories"

    id  = Column(Integer, primary_key=True)

    assignment_id  = Column(Integer, ForeignKey('assignments.id'))

    path = Column(String(100))

    extra_credit = Column(Boolean)
    graded       = Column(Boolean)
    hidden       = Column(Boolean)

    def __init__(self, **kwargs):
        self.set_dict(**kwargs)

    def set_dict(self, path="", extra_credit=False, graded=True, hidden=False):
        self.extra_credit = extra_credit
        self.path = path
        self.graded = graded
        self.hidden = hidden

    def __json__(self):
        return {
            "id":self.id,
            "path":self.path,
            "extra_credit":self.extra_credit,
            "graded":self.graded,
            "hidden":self.hidden
        }

    def __str__(self):
        return "<AssignmentAssetDirectory '{}'{}{}>".format(self.path,
                " Graded" if self.graded else " Ungraded",
                " Hidden" if self.hidden else "")

    def tests(self):
        '''
        Returns an array of TestScenes, one for each scene file in this
        directory (and all its subdirectories).
        '''
        tests = []

        for root, dirnames, filenames in os.walk(self.path):
            for filename in filenames:
                if (os.path.splitext(filename)[1] == TEST_EXTENSION):
                    tests.append(
                        TestScene(os.path.join(root, filename),
                             graded=self.graded,
                             hidden=self.hidden))

        return tests

class Submission(Base):
    '''
    Metadata associated with a student's submitted assignment.
    '''
    __tablename__ = "submissions"

    id  = Column(Integer, primary_key=True)
    assignment_id  = Column(Integer, ForeignKey('assignments.id'))
    student_id     = Column(Integer, ForeignKey('students.id'))

    difficulty_rating   = Column(Integer)
    fun_rating          = Column(Integer)
    frustration_rating  = Column(Integer)

    days_spent_on = Column(Integer)

    comments = Column(Text)

    submission_time = Column(DateTime, default=datetime.datetime.utcnow)

    test_runs = relationship("TestSceneRun", backref='submission')

    def __init__(self, assignment=None, student=None, difficulty_rating=None,
            fun_rating=None, frustration_rating=None, days_spent_on=None,
            comments=None):
        if assignment is not None:
            self.assignment_id = assignment.id
        else:
            self.assignment_id = None

        if student is not None:
            self.student_id = student.id
        else:
            self.student_id = None

        self.difficulty_rating = difficulty_rating
        self.fun_rating = fun_rating
        self.frustration_rating = frustration_rating
        self.comments = comments
        self.days_spent_on = days_spent_on

    def __str__(self):
        return "<Submission by {}: {} / {}>".format(self.student.uni,
                len(self.passed_runs()), len(self.test_runs))

    def passed_runs(self):
        return filter(lambda tr: tr.success, self.test_runs)

    def grade(self):
        if len(self.test_runs) == 0:
            return None

        return len(self.passed_runs()) / float(len(self.test_runs))

class TestSceneRun(Base):
    __tablename__ = "test_scene_runs"

    id            = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"))

    scene_path    = Column(String)

    run_time      = Column(DateTime, default=datetime.datetime.utcnow)

    success       = Column(Boolean)

    def __init__(self, path="", success=None):
        self.scene_path = path
        self.success = success
        self.run_time = datetime.datetime.now()

def main():
    Base.metadata.create_all(engine)

if __name__ == '__main__':
    main()
