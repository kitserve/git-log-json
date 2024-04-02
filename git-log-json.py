#!/usr/bin/env python3
'''
Forensic tool for git repositories. Analyses a git repository and produces a JSON
file summarising each file change: the commit hash when the file was changed, the author, and the date of the commit.
'''
import argparse
import datetime
import git
import json
import os
import sys

__authors__   = ["Kitserve <kitserve at users dot noreply dot github dot com>"]
__copyright__ = "2024 Kitson Consulting Limited"
__group__     = "git-log-json"
__license__   = "GPLv3 or later"

def main(argv):
	argumentParser = argparse.ArgumentParser(description='Git commit analyser')
	argumentParser.add_argument('-p', '--path', help='Path to Git directory', required=True)
	argumentParser.add_argument('-b', '--branch', help='Branch to analyse, defaults to the current active branch', required=False)
	argumentParser.add_argument('-o', '--output-file', help='Name of analysis results file', required=True)
	argumentParser.add_argument('-d', '--debug', help='Output extra debugging information', default=False, action='store_true')
	args = vars(argumentParser.parse_args())

	# Validate args and exit if any are incorrect
	path = os.path.realpath(args['path'])

	if not os.path.isdir(path):
		print(f'{args["path"]} is not a directory. Terminating.')
		sys.exit(1)

	try:
		repo = git.Repo(path)
	except git.exc.InvalidGitRepositoryError:
		print(f'{path} is not a valid git repository. Terminating.')
		sys.exit(2)

	if args['debug']:
		print(f'Debug: repo "{path}" is {"not " if not repo.bare else ""}bare.')
		print(f'Debug: repo "{path}" is currently on branch "{repo.active_branch}".')

	# Warn if there are changes that haven't yet made it into Git history
	if repo.is_dirty():
		print(f'Warning: repo "{path}" is dirty. The following files have been modified:')
		for item in repo.index.diff(None):
			print(f' {item.a_path}')

	if len(repo.untracked_files):
		print(f'Warning: repo "{path}" contains the following untracked files:')
		for file in repo.untracked_files:
			print(f' {file}')

	# Default to current active branch
	if args['branch'] is None:
		branch = repo.active_branch

	# Check that the requested branch exists in the repo
	else:
		branch = None
		for ref in repo.references:
			if args['branch'] == 'main':
				if 'main' == ref.name:
					branch = 'main'
					break
				elif 'master' == ref.name:
					branch = 'master'
					break
			else:
				if args['branch'] == ref.name:
					branch = args['branch']
					break

		if not branch:
			print(f'Branch "{args["branch"]}" not found in repo "{path}". Terminating.')
			sys.exit(3)

	total_commits = 0
	total_revisions = 0

	first_commit = True

	with open(args['output_file'], 'w') as output_file:
		output_file.write('[')
		# iter_commits() returns an iterator rather than a list, so we need output each revision record as a separate JSON string
		for commit in repo.iter_commits(rev = branch):
			for file in commit.stats.files:
				if not first_commit:
					output_file.write(',')
				output_file.write(json.dumps({'revision': commit.hexsha, 'author': commit.author.name, 'email': commit.author.email, 'date': datetime.datetime.fromtimestamp(commit.committed_date).isoformat(), 'message': commit.message.strip(), 'modified': file, 'extension': os.path.splitext(file)[1]}))
				first_commit = False
				total_revisions += 1
			total_commits += 1
		output_file.write(']')

	if args['debug']:
		print(f'Debug: wrote {total_revisions} file modification record(s) from {total_commits} commit(s) in repo "{path}" on branch "{branch}" to JSON file "{args["output_file"]}".')

if __name__ == '__main__':
	main(sys.argv)
