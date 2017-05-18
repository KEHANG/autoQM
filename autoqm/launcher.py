
# connect to registration table

# search entries with status "job_created" 
# check the job input files are indeed there

# launch job, get jobid and update status "job_launched"
import os
import subprocess

import autoqm.utils
from autoqm.connector import saturated_ringcore_table

config = autoqm.utils.read_config()

def select_launch_target():
	"""
	This method is to inform job launcher which targets 
	to launch, which need meet two requirements:
	1. status is job_created
	2. job input files located as expected

	Returns a list of targets with necessary meta data
	"""
	limit = 10
	top_targets = list(saturated_ringcore_table.find({"status":"job_created"}).sort([('count', -1)]).limit(limit))

	selected_targets = []
	data_path = config['QuantumMechanicJob']['data_path']
	for target in top_targets:
		aug_inchi = str(target['aug_inchi'])
		spec_name = aug_inchi.replace('/', '_slash_')
		spec_path = os.path.join(data_path, spec_name)

		inp_file = os.path.join(spec_path, 'input.inp')
		submission_script_path = os.path.join(spec_path, 'submit.sl')
		if os.path.exists(inp_file) and os.path.exists(submission_script_path):
			selected_targets.append(target)

	print('Selected {0} targets to launch.'.format(len(selected_targets)))

	return selected_targets

def launch_jobs():
	"""
	This method launches job with following steps:
	1. select jobs to launch
	2. go to each job folder
	3. launch them with "sbatch submit.sl > job_id.txt"
	4. get job id
	5. update status "job_launched"
	"""
	# 1. select jobs to launch
	targets = select_launch_target()

	# 2. go to each job folder
	data_path = config['QuantumMechanicJob']['data_path']
	for target in targets:
		aug_inchi = str(target['aug_inchi'])
		spec_name = aug_inchi.replace('/', '_slash_')
		spec_path = os.path.join(data_path, spec_name)

		os.chdir(spec_path)

		# 3. launch them with "sbatch submit.sl > job_id.txt"
		# maybe I should create a launch.sh which has command
		# sbatch submit.sl > job_id.txt
		launch_script = os.path.join(spec_path, 'launch.sh')
		with open(launch_script, 'w') as f_in:
			f_in.write('sbatch submit.sl > job_id.txt')
		
		commands = ['bash', launch_script]
		subprocess.Popen(commands)

		# 4. get job id from txt "Submitted batch job 5022607"
		job_id_file = os.path.join(spec_path, 'job_id.txt')
		with open(job_id_file, 'r') as f_out:
			for line in f_out:
				if line and "Submitted batch job" in line:
					job_id = re.sub('[A-Za-z\s]*', '', "Submitted batch job 5022607")
					print("job id is {0}".format(job_id))
		
	# 5. update status "job_launched"

