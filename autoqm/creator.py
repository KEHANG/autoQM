import re
import os
from rdkit import Chem
from rdkit.Chem import AllChem

from rmgpy.molecule import Molecule

import autoqm.utils
import autoqm.connector

def select_run_target():
	"""
	This method is to inform job creator which targets 
	to run.

	Returns a list of targets with necessary meta data
	"""
	# connect to central database registration table
	auth_info = autoqm.utils.get_TCD_authentication_info()
	tcdi = autoqm.connector.ThermoCentralDatabaseInterface(*auth_info)

	tcd =  getattr(tcdi.client, 'thermoCentralDB')
	saturated_ringcore_table = getattr(tcd, 'saturated_ringcore_table')

	limit = 10
	top_ringcores = list(saturated_ringcore_table.find({"status":"pending"}).sort([('count', -1)]).limit(limit))

	return top_ringcores

def generate_input_from_smiles(smiles, 
								spec_name,
								spec_path, 
								memory='1500mb', 
								procs_num='32', 
								level_theory='um062x/cc-pvtz'):
	"""
	This method writes quantum mechanics input file, given
	smiles and species name.

	Currently only support Gaussian format.
	"""
	
	input_string = ""
	# calculate charge and multiplicity
	rmg_mol = Molecule().fromSMILES(smiles)
	input_string += "{charge}   {mult}\n".format(charge=0, 
												mult=(rmg_mol.getRadicalCount() + 1) )

	# create rdkit mol from smiles
	mol2d = Chem.MolFromSmiles(smiles)

	# optimze geometry a little bit
	mol3d = Chem.AddHs(mol2d)
	AllChem.EmbedMolecule(mol3d)
	AllChem.UFFOptimizeMolecule(mol3d) 

	# save mol files
	mol_file_path = os.path.join(spec_path, '{0}.mol'.format(spec_name))
	with open(mol_file_path, 'w') as mol_file:
		mol_file.write(Chem.MolToMolBlock(mol3d))

	# parse the mol files to get xyz coordinates
	xyz_coord = []
	atomline = re.compile('\s*([\- ][0-9.]+\s+[\-0-9.]+\s+[\-0-9.]+)\s+([A-Za-z]+)')
	with open(mol_file_path, 'r') as mol_file:
		for line in mol_file:
			match = atomline.match(line)
			if match:
				xyz_coord.append("{0:8s} {1}".format(match.group(2), match.group(1)))

	xyz_coord.append('')
	input_string += '\n'.join(xyz_coord)

	# start writing with qm input head
	qm_input_head_string = """%%chk=%s.chk
%%mem=%s
%%nproc=%s
# opt freq %s""" % (spec_name, memory, procs_num, level_theory)

	inp_file = os.path.join(spec_path, '{0}.inp'.format(spec_name))
	
	with open(inp_file, 'w+') as fout:
		fout.write(qm_input_head_string)
		fout.write('\n\n' + spec_name + '\n\n')
		fout.writelines(input_string)
		fout.write('\n')

def generate_submission_script(spec_name,
								spec_path,
								partition='regular', 
								nodes_num='1', 
								walltime='10:00:00', 
								software='g09'):
	
	qm_submission_head_string = """#!/bin/bash -l
#SBATCH -p %s
#SBATCH -N %s
#SBATCH -t %s
#SBATCH -J %s
#SBATCH -C haswell
#SBATCH -o out.log\n""" % ('regular', nodes_num, walltime, spec_name)
	
	submission_script_path = os.path.join(spec_path, 'submit.sl')
	with open(submission_script_path, 'w+') as fout:
		fout.write(qm_submission_head_string)
		fout.write('\nmodule load {0}\n\n'.format(software))
		fout.write('{0} '.format(software) + spec_name + '.inp' + '\n')

def create_jobs():

	config = autoqm.utils.read_config()
	# select target to run
	targets = select_run_target()

	# generate qm jobs
	data_path = config['QuantumMechanicJob']['data_path']
	for target in targets:
		smiles = str(target['SMILES_input'])
		aug_inchi = str(target['aug_inchi'])
		spec_name = aug_inchi.replace('/', '_slash_')
		spec_path = os.path.join(data_path, spec_name)

		if not os.path.exists(spec_path):
			os.mkdir(spec_path)

		# generate qm job input file
		generate_input_from_smiles(smiles, spec_name, spec_path)

		# generate qm job submission file
		generate_submission_script(spec_name, spec_path)
