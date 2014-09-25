#!/usr/bin/env python

from models import Assignment, AssignmentAssetDirectory, Session
import dateutil.parser

def define_asset_directory():
    path = raw_input("Path to the directory: ")

    graded = 'y' in raw_input("Is this directory required for this deliverable [y/n]: ")
    hidden = 'y' in raw_input("Is this directory full of hidden scenes [y/n]: ")

    asset_directory = AssignmentAssetDirectory()

    asset_directory.path = path
    asset_directory.graded = graded
    asset_directory.hidden = hidden

    return asset_directory

def create_assignment():
    theme       = int(raw_input("Theme: "))
    milestone   = int(raw_input("Milestone: "))
    deliverable = int(raw_input("Deliverable: "))

    oracle_path   = raw_input("Path to the oracle: ")
    template_path = raw_input("Path to the assignment directory: ")

    start_date  = dateutil.parser.parse(raw_input("Start date (YYYY-MM-DD): "))
    due_date    = dateutil.parser.parse(raw_input("Date on which it's due at 11:59 PM (YYYY-MM-DD): "))

    response = True

    assignment_asset_directories = []
    while response:
        response = 'y' in raw_input("Add another asset directory [y/n]: ")
        if response:
            assignment_asset_directories.append(define_asset_directory())

    define_assignment(theme=theme, milestone=milestone,
            deliverable=deliverable, oracle_path=oracle_path,
            template_path=template_path, start_date=start_date,
            due_date=due_date,
            assignment_asset_directories= assignment_asset_directories)

def define_assignment(theme=None, milestone=None, deliverable=None,
        oracle_path=None, template_path=None, start_date=None, due_date=None,
        assignment_asset_directories=[]):

    session = Session()

    assignment = Assignment(
            theme=theme,
            milestone=milestone,
            deliverable=deliverable,
            oracle_path=oracle_path,
            template_path=template_path,
            start_date=start_date,
            due_date=due_date)

    session.add(assignment)
    session.flush()

    for asset in assignment_asset_directories:
        asset.assignment_id = assignment.id
        session.add(asset)

    session.commit()

DEFAULT_ASSET_DIRECTORY        = "/home/cs4167/assets/t{0}m{1}/Deliverable{2}/"
DEFAULT_HIDDEN_ASSET_DIRECTORY = "/home/cs4167/grading/hiddenassets/t{0}m{1}/Deliverable{2}/"

def simple_define_assignment(theme=None, milestone=None):
    if theme is None:
        theme = int(raw_input("Theme: "))

    if milestone is None:
        milestone = int(raw_input("Milestone: "))

    oracle_path   = raw_input("Path to the oracle: ")
    template_path = raw_input("Path to the assignment directory: ")

    start_date  = dateutil.parser.parse(raw_input("Start date (YYYY-MM-DD): "))

    d1_due_date    = dateutil.parser.parse(raw_input("Date on which Deliverable 1 is due at 11:59 PM (YYYY-MM-DD): "))
    d2_due_date    = dateutil.parser.parse(raw_input("Date on which Deliverable 2 is due at 11:59 PM (YYYY-MM-DD): "))
    d3_due_date    = dateutil.parser.parse(raw_input("Date on which Deliverable 3 is due at 11:59 PM (YYYY-MM-DD): "))

    start_dates = [start_date, start_date, start_date]
    due_dates = [d1_due_date, d2_due_date, d3_due_date]

    assets = [
        [
            # For Deliverable 1, Deliverable 1 assets are graded
            AssignmentAssetDirectory(DEFAULT_ASSET_DIRECTORY.format(theme, milestone, 1), graded=True, hidden=False),
            # For Deliverable 1, Deliverable 1 hidden assets are graded
            AssignmentAssetDirectory(DEFAULT_HIDDEN_ASSET_DIRECTORY.format(theme, milestone, 1), graded=True, hidden=True),
            # For Deliverable 1, Deliverable 2 assets are not graded, but the results are shown
            AssignmentAssetDirectory(DEFAULT_ASSET_DIRECTORY.format(theme, milestone, 2), graded=False, hidden=False),
        ],
        [
            AssignmentAssetDirectory(DEFAULT_ASSET_DIRECTORY.format(theme, milestone, 2), graded=True, hidden=False),
            AssignmentAssetDirectory(DEFAULT_HIDDEN_ASSET_DIRECTORY.format(theme, milestone, 2), graded=True, hidden=True),
        ],
        [] # Creative deliverable has no tests
    ]

    for i in range(3):
        define_assignment(
            theme=theme, 
            milestone=milestone,
            deliverable=i+1,
            oracle_path=oracle_path, 
            template_path=template_path,
            start_date=start_dates[i], 
            due_date=due_dates[i],
            assignment_asset_directories=assets[i])

def print_all_assignments():
    session = Session()
    assignments = session.query(Assignment).all()
    for a in assignments:
        print(a)


def main():
    simple_define_assignment()

if __name__ == '__main__':
    main()
