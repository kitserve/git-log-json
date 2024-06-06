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

	# @see https://github.com/gitpython-developers/GitPython/issues/364
	# @see https://stackoverflow.com/questions/33916648/get-the-diff-details-of-first-commit-in-gitpython
	EMPTY_TREE_SHA = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'

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
		if args['debug']:
			output_file.write('\n')
		# iter_commits() returns an iterator rather than a list, so we need output each revision record as a separate JSON string
		for commit in repo.iter_commits(rev = branch):
			if len(commit.parents) == 0:
				previous_commit = None
			else:
				previous_commit = commit.parents[0].tree
			for file in commit.stats.files:
				if not first_commit:
					output_file.write(',')
					if args['debug']:
						output_file.write('\n')
				status = repo.git.diff('--name-status', previous_commit, file).split('\t')[0]
				if status == '':
					status = 'Added'
					lines_added, lines_removed, dummy = repo.git.diff(EMPTY_TREE_SHA, file, numstat=True).split('\t')
				elif status == 'A':
					status = 'Added'
					lines_added, lines_removed, dummy = repo.git.diff(previous_commit, file, numstat=True).split('\t')
				elif status == 'C':
					status = 'Copied'
					lines_added, lines_removed, dummy = repo.git.diff(previous_commit, file, numstat=True).split('\t')
				elif status == 'D':
					status = 'Deleted'
					lines_added, lines_removed, dummy = repo.git.diff(previous_commit, file, numstat=True).split('\t')
				elif status == 'M':
					status = 'Modified'
					lines_added, lines_removed, dummy = repo.git.diff(previous_commit, file, numstat=True).split('\t')
				elif status == 'R':
					status = 'Renamed'
					lines_added = 0
					lines_removed = 0
				elif status == 'T':
					status = 'Type (mode) changed'
					lines_added = 0
					lines_removed = 0
				elif status == 'U':
					status = 'Unmerged'
					lines_added = 0
					lines_removed = 0
				elif status == 'X':
					status = 'Unknown'
					lines_added = None
					lines_removed = None
				elif status == 'B':
					status = 'Broken pairing'
					lines_added = None
					lines_removed = None
				try:
					lines_added = int(lines_added)
				except:
					pass
				try:
					lines_removed = int(lines_removed)
				except:
					pass
				if args['debug']:
					output_file.write(json.dumps({'revision': commit.hexsha, 'author': commit.author.name, 'email': commit.author.email, 'date': datetime.datetime.fromtimestamp(commit.committed_date).isoformat(), 'message': commit.message.strip(), 'modified': file, 'extension': os.path.splitext(file)[1], 'status': status, 'lines_added': lines_added, 'lines_removed': lines_removed}, indent=1))
				else:
					output_file.write(json.dumps({'revision': commit.hexsha, 'author': commit.author.name, 'email': commit.author.email, 'date': datetime.datetime.fromtimestamp(commit.committed_date).isoformat(), 'message': commit.message.strip(), 'modified': file, 'extension': os.path.splitext(file)[1], 'status': status, 'lines_added': lines_added, 'lines_removed': lines_removed}))
				first_commit = False
				total_revisions += 1
			total_commits += 1
		if args['debug']:
			output_file.write('\n')
		output_file.write(']')
		if args['debug']:
			output_file.write('\n')

	if args['debug']:
		print(f'Debug: wrote {total_revisions} file modification record(s) from {total_commits} commit(s) in repo "{path}" on branch "{branch}" to JSON file "{args["output_file"]}".')

if __name__ == '__main__':
	main(sys.argv)
