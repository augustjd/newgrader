#!/usr/bin/env python

import json
from models import Session, Assignment, AssignmentAssetDirectory
import sys
import json
import datetime
import dateutil.parser

class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)

def export_assignments(out_filepath):
    s = Session()
    assignments = s.query(Assignment).all()
    assignment_jsons = [a.__json__() for a in assignments]

    with open(out_filepath, 'w') as f:
        s = json.dumps(assignment_jsons, indent=2, cls=DateEncoder)
        f.write(s)

def set_or_create_assignment(assignment_dict, session=None):
    if session is None:
        session = Session()

    assignment_dict['start_date'] = dateutil.parser.parse(assignment_dict['start_date'])
    assignment_dict['due_date'] = dateutil.parser.parse(assignment_dict['due_date'])

    directories = assignment_dict.pop('asset_directories')

    existing = session.query(Assignment).get(assignment_dict.get('id', -1))
    if existing is None:
        session.add(Assignment(**assignment_dict))
        session.flush() # so that existing.id is defined.
    else:
        del assignment_dict['id']
        existing.set_dict(**assignment_dict)

    for directory in directories:
        set_or_create_assignment_asset_directory(existing, directory, session)

    session.commit()

def set_or_create_assignment_asset_directory(parent_assignment, directory_dict, session=None):
    if session is None:
        session = Session()

    existing_dir = session.query(AssignmentAssetDirectory).get(directory_dict.get('id', -1))
    if existing_dir is None:
        existing_dir = AssignmentAssetDirectory(**directory_dict)
        session.add(existing_dir)
    else:
        del directory_dict['id']
        existing_dir.set_dict(**directory_dict)

    existing_dir.assignment_id = parent_assignment.id

    session.commit()

def import_assignments(in_filepath):
    s = Session()
    obj = json.loads(open(in_filepath).read())

    for assignment in obj:
        set_or_create_assignment(assignment, s)

    s.commit()

def main():
    if len(sys.argv) < 2:
        print "Usage: {} <input JSON filepath>"
        print "       {} -o <output JSON filepath>"
        sys.exit(0)

    if sys.argv[1] == '-o':
        if len(sys.argv) < 3:
            print "Usage: {} -o <output JSON filepath>"
            sys.exit(0)

        export_assignments(sys.argv[2])
    else:
        import_assignments(sys.argv[1])

if __name__ == '__main__':
    main()
