import sublime
import sublime_plugin
import requests
import json
import adal
import webbrowser
import base64
import os
import datetime
from pprint import pprint

class SolutionSettings:
	debug = False
	loaded = False
	authority_host_url = 'https://login.microsoftonline.com'
	client_id = '04b07795-8ddb-461a-bbee-02f9e1bf7b46' # AzureCLI
	settings_filename = 'D365 Web Resources-settings.json'
	resource_url = ''
	azure_directory_name = ''
	azure_tenant_id = ''
	authority_uri = ''
	web_api_version = ''
	request_headers = ''
	web_api_url = ''
	json = ''
	retry_once = True
	selected_path = ''
	settings_path = ''
	settings_level = 0
	retrieve_managed_solutions = False
	retrieve_web_resource_types = ''
	auto_open_browser_login = True
	file_backup_folder = ''

def RetrieveSolutions():
	query = ''
	if(SolutionSettings.retrieve_managed_solutions == True):
		query = '/solutions?$filter=ismanaged eq true and isvisible eq true'
	else:
		query = '/solutions?$filter=ismanaged eq false and isvisible eq true'
	query_results = requests.get(SolutionSettings.web_api_url + query, headers = SolutionSettings.request_headers)

	if(SolutionSettings.debug == True):
		pprint(vars(query_results))

	if(query_results.status_code == 401):
		CreateRequestHeaders(CreateToken())
		RetrieveSolutions()
		return
	elif(query_results.status_code != 200):
		return

	results = query_results.json()

	solutions = []
	for idx, item in enumerate(results['value']):
		unique_name = item['uniquename']
		friendly_name = item['friendlyname']
		solution_id = item['solutionid']
		solutions.append(friendly_name)

	# Open dialog
	sublime.active_window().show_quick_panel(solutions, RetrieveSolutionIndex, sublime.MONOSPACE_FONT)
	return

def RetrieveSolutionIndex(index):
	if(index == -1):
		return

	query = ''
	if(SolutionSettings.retrieve_managed_solutions == True):
		query = '/solutions?$filter=ismanaged eq true and isvisible eq true'
	else:
		query = '/solutions?$filter=ismanaged eq false and isvisible eq true'
	query_results = requests.get(SolutionSettings.web_api_url + query, headers = SolutionSettings.request_headers)

	if(SolutionSettings.debug == True):
		pprint(vars(query_results))

	if(query_results.status_code == 401):
		CreateRequestHeaders(CreateToken())
		RetrieveSolutions()
		return
	elif(query_results.status_code != 200):
		return

	try:
		results = query_results.json()
		if(SolutionSettings.debug == True):
			pprint(results)

		print('Solution folders created/updated:')
		for idx, item in enumerate(results['value']):
			if(idx != index):
				continue

			unique_name = item['uniquename']
			friendly_name = item['friendlyname']
			solution_id = item['solutionid']
			print('\t' + unique_name)

			if(SolutionSettings.debug == True):
				print('Make dir: ' + os.path.dirname(SolutionSettings.settings_path + '/' + unique_name + '/'))
			os.makedirs(os.path.dirname(SolutionSettings.settings_path + '/' + unique_name + '/'), exist_ok=True)

			SolutionSettings.json['webresource_data']['solutions'][unique_name] = {}
			SolutionSettings.json['webresource_data']['solutions'][unique_name]['solutionid'] = solution_id
			SolutionSettings.json['webresource_data']['solutions'][unique_name]['friendlyname'] = friendly_name

			SaveSolutionSettings(SolutionSettings.json)

			SolutionSettings.selected_path = SolutionSettings.selected_path + '/' + unique_name
			DownloadWebResources()

	except Exception as error:
		message = 'Error - Could not retrieve solutions: ' + repr(error)
		sublime.message_dialog(message)
		raise Exception(message)

def UploadWebResource():
	try:
		path_info = DirectoryPathToFilename(SolutionSettings.selected_path)

		if(SolutionSettings.debug == True):
			print(path_info)

		if not path_info['name'] in SolutionSettings.json['webresource_data']['files']:
			message = 'This is a new file.\n\nWould you like to create this as a new Web Resource to current solution?'
			ret = sublime.ok_cancel_dialog(message)
			if not ret:
				return
			else:
				# Upload file to server as a Web Resource
				solution_name = path_info['name'].split('/')[0]
				file_name = path_info['name'][len(solution_name)+1:]
				solution_path = FindSettingsFile(SolutionSettings.selected_path)['path'] + '/' + solution_name

				try:
					solution_id = SolutionSettings.json['webresource_data']['solutions'][solution_name]['solutionid']
					if(solution_id == '' or len(solution_id) != 36):
						raise Exception('')
				except Exception as error:
					message = 'Error - Could not find solution "' + solution_name + '" from settings file.'
					sublime.message_dialog(message)
					return

				url = SolutionSettings.web_api_url + '/webresourceset'

				file_content = open(SolutionSettings.selected_path, 'r', encoding='utf-8')
				content_encoded = base64.b64encode(bytes(file_content.read(), 'utf-8')).decode('utf-8')

				webresource_type = None
				if(file_name[-5:] == '.html'):
					webresource_type = 1
				elif(file_name[-4:] == '.css'):
					webresource_type = 2
				elif(file_name[-3:] == '.js'):
					webresource_type = 3
				elif(file_name[-4:] == '.xml'):
					webresource_type = 4
				elif(file_name[-4:] == '.svg'):
					webresource_type = 11
				elif(file_name[-5:] == '.resx'):
					webresource_type = 12

				if(webresource_type == None):
					message = 'File extension is not supported.'
					sublime.message_dialog(message)
					return

				# Create new Web Resource
				entity = {
					'name': file_name,
					'displayname': file_name,
					'content': content_encoded,
					'webresourcetype': str(webresource_type)
				}

				query_results = requests.post(url, headers=SolutionSettings.request_headers, data=json.dumps(entity))

				if(SolutionSettings.debug == True):
					pprint(vars(query_results))

				if(query_results.status_code == 401):
					CreateRequestHeaders(CreateToken())
					UploadWebResource()
					return
				elif(query_results.status_code != 204):
					message = 'Error - ' + json.loads(query_results._content.decode('UTF-8'))['error']['message']
					sublime.message_dialog(message)
					return

				entityId = query_results.headers['OData-EntityId']
				webresource_id = entityId[entityId.find('(')+1:entityId.find(')')]

				date_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
				print('Web Resource Saved: ' + date_time)

				# Publsh Web Resource
				parameters = {
					"ParameterXml": "<importexportxml>\
						<webresources>\
							<webresource>{" + webresource_id + "}</webresource>\
						</webresources>\
					</importexportxml>"
				}

				post_request = requests.post(SolutionSettings.web_api_url + '/PublishXml', headers=SolutionSettings.request_headers, data=json.dumps(parameters))

				if(SolutionSettings.debug == True):
					pprint(vars(post_request))

				date_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
				print('Web Resource Published: ' + date_time)

				# Add Web Resource to solution
				# Metadata source: /api/data/v9.1/$metadata
				# Component Types: https://docs.microsoft.com/en-us/dynamics365/customer-engagement/web-api/solutioncomponent?view=dynamics-ce-odata-9
				url = SolutionSettings.web_api_url + '/AddSolutionComponent'

				entity = {
					'ComponentId': webresource_id,
					'SolutionUniqueName': solution_name,
					'ComponentType': 61,
					'AddRequiredComponents': False
				}

				query_results = requests.post(url, headers=SolutionSettings.request_headers, data=json.dumps(entity))

				if(SolutionSettings.debug == True):
					pprint(vars(query_results))

				if(query_results.status_code != 200):
					message = 'Error - ' + json.loads(query_results._content.decode('UTF-8'))['error']['message']
					sublime.message_dialog(message)
					return

				date_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
				sublime.active_window().status_message('Web Resource saved, published and added to solution: ' +  date_time)

				SolutionSettings.selected_path = solution_path
				DownloadWebResources()
				return

		webresource_id = SolutionSettings.json['webresource_data']['files'][path_info['name']]['webresource_id']
		webresource_idunique = SolutionSettings.json['webresource_data']['files'][path_info['name']]['webresource_idunique']

		server_webresource_info = GetWebResourceById(webresource_id)
		if(server_webresource_info == False):
			message = 'Error - Could not find Web Resource from server, has it been deleted?'
			sublime.message_dialog(message)
			return

		# Backup to folder
		try:
			if(SolutionSettings.file_backup_folder != ''):
				file_content_server = base64.b64decode(server_webresource_info['content']).decode('utf-8', 'ignore')
				file_content_local = open(SolutionSettings.selected_path, 'r', encoding='utf-8').read()
				date_time = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
				file_name = server_webresource_info['name']
				if '/' in file_name:
					if(SolutionSettings.debug == True):
						print('Make dir: ' + os.path.dirname(SolutionSettings.file_backup_folder + '/' + file_name))
					print('Creating.. ' + SolutionSettings.file_backup_folder + '/' + file_name)
					os.makedirs(os.path.dirname(SolutionSettings.file_backup_folder + '/' + file_name), exist_ok=True)
				with open(SolutionSettings.file_backup_folder + '/' + file_name + '_server_' + date_time, 'wb') as f:
					f.write(file_content_server.encode('utf-8'))
				with open(SolutionSettings.file_backup_folder + '/' + file_name + '_local_' + date_time, 'wb') as f:
					f.write(file_content_local.encode('utf-8'))
		except Exception as error:
			message = 'Error - Could not create backup, please ensure that the directory exists:\n\n' + SolutionSettings.file_backup_folder + '\n\nError code: ' + repr(error)
			sublime.message_dialog(message)
			return

		if(server_webresource_info['webresourceidunique'] != webresource_idunique):
			message = 'There is a conflict between server and local file.\n\nServer file is newer, modified on:\n' + server_webresource_info['modifiedon@OData.Community.Display.V1.FormattedValue'] + '.\n\nDo you really want to overwrite server file?'
			ret = sublime.ok_cancel_dialog(message)
			if not ret:
				return

		url = SolutionSettings.web_api_url + '/webresourceset(' + webresource_id + ')'

		file_content = open(SolutionSettings.selected_path, 'r', encoding='utf-8')
		content_encoded = base64.b64encode(bytes(file_content.read(), 'utf-8')).decode('utf-8')
		if(SolutionSettings.debug == True):
			print(content_encoded)

		entity = {
			"content": content_encoded,
		}

		query_results = requests.patch(url, headers=SolutionSettings.request_headers, data=json.dumps(entity))

		if(query_results.status_code == 401):
			CreateRequestHeaders(CreateToken())
			UploadWebResource()
			return
		elif(query_results.status_code != 204):
			return

		if(SolutionSettings.debug == True):
			pprint(vars(query_results))

		date_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
		print('Web Resource Saved: ' + date_time)

		parameters = {
			"ParameterXml": "<importexportxml>\
				<webresources>\
					<webresource>{" + webresource_id + "}</webresource>\
				</webresources>\
			</importexportxml>"
		}

		post_request = requests.post(SolutionSettings.web_api_url + '/PublishXml', headers=SolutionSettings.request_headers, data=json.dumps(parameters))

		if(SolutionSettings.debug == True):
			pprint(vars(post_request))

		date_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
		print('Web Resource Published: ' + date_time)

		server_webresource_info = GetWebResourceById(webresource_id)
		if(server_webresource_info == False):
			message = 'Error - Could not find Web Resource from server, has it been deleted?'
			sublime.message_dialog(message)
			return

		SolutionSettings.json['webresource_data']['files'][path_info['name']]['webresource_idunique'] = server_webresource_info['webresourceidunique']
		SaveSolutionSettings(SolutionSettings.json)

		date_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
		sublime.active_window().status_message('Web Resource saved and published: ' +  date_time)

	except Exception as error:
		message = 'Error - An error occurred while uploading Web Resource: ' + repr(error)
		sublime.message_dialog(message)
		raise Exception(message)

def GetWebResourceById(webresource_id):
	query = '/webresourceset?fetchXml=\
		<fetch mapping="logical" count="500" version="1.0">\
			<entity name="webresource">\
				<all-attributes />\
				<filter type="and">\
					<condition attribute="webresourceid" operator="eq" value="' + webresource_id + '" />\
				</filter>\
			</entity>\
		</fetch>'
	query_results = requests.get(SolutionSettings.web_api_url + query, headers=SolutionSettings.request_headers)

	if(SolutionSettings.debug == True):
		pprint(vars(query_results))

	if(query_results.status_code == 401):
		CreateRequestHeaders(CreateToken())
		return GetWebResourceById(webresource_id)
	elif(query_results.status_code != 200):
		return False

	try:
		results = query_results.json()

		if(SolutionSettings.debug == True):
			pprint(results)

		for idx, item in enumerate(results['value']):
			return item

	except Exception as error:
		message = 'Error - Could not retrieve Web Resource: ' + repr(error)
		sublime.message_dialog(message)
		raise Exception(message)

	return False


def DownloadWebResources():
	solution_name = os.path.basename(SolutionSettings.selected_path)

	web_resource_types = ''
	if(SolutionSettings.retrieve_web_resource_types != ''):
		arr = SolutionSettings.retrieve_web_resource_types.split(',')
		for item in arr:
			if item.isdigit():
				web_resource_types = web_resource_types + '<condition attribute="webresourcetype" operator="eq" value="' + item + '" />'

	query = '/webresourceset?fetchXml=\
		<fetch mapping="logical" count="500" version="1.0">\
			<entity name="webresource">\
				//<all-attributes />\
				<attribute name="name" />\
				<attribute name="content" />\
				<attribute name="webresourceidunique" />\
				<filter type="or">\
					' + web_resource_types + '\
				</filter>\
				<link-entity name="solutioncomponent" from="objectid" to="webresourceid">\
					<filter>\
						<condition attribute="solutionidname" operator="eq" value="' + solution_name + '" />\
					</filter>\
				</link-entity>\
			</entity>\
		</fetch>'
	query_results = requests.get(SolutionSettings.web_api_url + query, headers=SolutionSettings.request_headers)

	if(SolutionSettings.debug == True):
		pprint(vars(query_results))

	if(query_results.status_code == 401):
		CreateRequestHeaders(CreateToken())
		DownloadWebResources()
		return
	elif(query_results.status_code != 200):
		return

	try:
		results = query_results.json()
		if(SolutionSettings.debug == True):
			pprint(results)

		print('Found files:')
		counter = 1
		for idx, item in enumerate(results['value']):
			file_name = item['name']
			webresource_id = item['webresourceid']
			webresource_idunique = item['webresourceidunique']

			file_content = base64.b64decode(item['content']).decode('utf-8', 'ignore')
			print ('\t' + file_name)
			if '/' in file_name:
				if(SolutionSettings.debug == True):
					print('Make dir: ' + os.path.dirname(SolutionSettings.selected_path + '/' + file_name))
				os.makedirs(os.path.dirname(SolutionSettings.selected_path + '/' + file_name), exist_ok=True)
			with open(SolutionSettings.selected_path + '/' + file_name, 'wb') as f:
				f.write(file_content.encode("utf-8"))

			SolutionSettings.json['webresource_data']['files'][solution_name + '/' + file_name] = {}
			SolutionSettings.json['webresource_data']['files'][solution_name + '/' + file_name]['webresource_id'] = webresource_id
			SolutionSettings.json['webresource_data']['files'][solution_name + '/' + file_name]['webresource_idunique'] = webresource_idunique
		SaveSolutionSettings(SolutionSettings.json)

		date_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
		sublime.active_window().status_message('Web Resources downloaded from server: ' +  date_time)

	except Exception as error:
		message = 'Error - Could not download web resources: ' + repr(error)
		sublime.message_dialog(message)
		raise Exception(message)


def CreateToken():
	if(SolutionSettings.retry_once == False):
		message = 'Error: Could not create token - too many retries'
		sublime.message_dialog(message)
		raise Exception(message)

	SolutionSettings.retry_once = False
	SolutionSettings.authority_uri = SolutionSettings.authority_host_url + '/' + SolutionSettings.azure_tenant_id
	context = adal.AuthenticationContext(SolutionSettings.authority_uri, validate_authority=None)

	try:
		code = context.acquire_user_code(SolutionSettings.resource_url, SolutionSettings.client_id)
	except Exception as error:
		message = 'Error: Could not connect to: ' + SolutionSettings.resource_url + '\n\nEnsure that URL is correct and that a Azure Directory Name have been added to settings file.'
		sublime.message_dialog(message)
		raise Exception(message)

	if(SolutionSettings.auto_open_browser_login == True):
		webbrowser.open(code['verification_url'], new=2) # https://microsoft.com/devicelogin
	else:
		print('Open Web Page: https://microsoft.com/devicelogin')

	if(SolutionSettings.debug == True):
		print(code['message'])
		pprint(code)

	print('\nLogin code:\n\t' + code['user_code'] + '\n')
	sublime.set_clipboard(code['user_code'])

	try:
		mgmt_token = context.acquire_token_with_device_code(SolutionSettings.resource_url, code, SolutionSettings.client_id)
		token = mgmt_token['accessToken']

		if(SolutionSettings.debug == True):
			print(token)

		SolutionSettings.json['webresource_data']['o365token'] = token
		SolutionSettings.token_id = token;
		SaveSolutionSettings(SolutionSettings.json)

		return token
	except Exception as error:
		print('Error - Could not create token: ' + repr(error))

def CreateRequestHeaders(token):
	SolutionSettings.request_headers = {
	    'Authorization': 'Bearer ' + token,
	    'OData-MaxVersion': '4.0',
	    'OData-Version': '4.0',
	    'Accept': 'application/json',
	    'Content-Type': 'application/json; charset=utf-8',
	    'Prefer': 'odata.maxpagesize=500',
	    'Prefer': 'odata.include-annotations=OData.Community.Display.V1.FormattedValue'
	}

def DirectoryPathToFilename(path):
	path_suffix = ''
	file_name = ''
	for level in range(10):
		if(file_name == ''):
			file_name = os.path.basename(os.path.normpath(path + '/' + path_suffix))
		else:
			file_name = os.path.basename(os.path.normpath(path + '/' + path_suffix)) + '/' + file_name
		if(os.path.isfile(path + '/../' + path_suffix + SolutionSettings.settings_filename) == True):
			return { 'name': file_name, 'level': level }
		else:
			path_suffix = path_suffix + '../'
	return { 'name': '', 'level': -1 }

def FindSettingsFile(param_path = '', search_max_levels = 10):
	path_suffix = ''

	for level in range(search_max_levels):
		if(param_path != ''):
			cur_path = param_path + '/' + path_suffix + SolutionSettings.settings_filename
		else:
			cur_path = SolutionSettings.selected_path + '/' + path_suffix + SolutionSettings.settings_filename
		if(os.path.isfile(cur_path) == True):
			return { 'path': os.path.dirname(cur_path), 'solution_name': os.path.dirname(cur_path), 'level': level }
		else:
			path_suffix = path_suffix + '../'
	return { 'path': '', 'level': -1 }

def LoadSolutionSettings(ignoreNotFound = False):
	try:
		with open(SolutionSettings.settings_path + '/' + SolutionSettings.settings_filename, 'r', encoding='utf-8') as f:
			return json.load(f)
	except Exception as error:
		if(ignoreNotFound == False):
			message = type(error).__name__ + ':\n' + SolutionSettings.settings_path + '/' + SolutionSettings.settings_filename
			sublime.message_dialog(message)
			raise Exception(message)
	return None

def SaveSolutionSettings(data):
	with open(SolutionSettings.settings_path + '/' + SolutionSettings.settings_filename, 'w', encoding='utf-8') as f:
	    json.dump(data, f, sort_keys=True, indent = 4)

def RetrieveTenantId():
	url = 'https://login.windows.net/' + SolutionSettings.azure_directory_name + '.onmicrosoft.com/.well-known/openid-configuration'
	result = requests.get(url).json()

	if 'authorization_endpoint' in result:
		uuid = result['authorization_endpoint'][26:62]
		print('Found Tenant ID:\n\t' + uuid)
		SolutionSettings.azure_tenant_id = uuid
		SolutionSettings.json['organization_settings']['azure_tenant_id'] = SolutionSettings.azure_tenant_id
		SaveSolutionSettings(SolutionSettings.json)
		return True
	return False

def LoadSettings():
	if int(sublime.version()) < 3000:
		message = 'Sorry, at this point only Sublime Text 3 and above is supported.'
		sublime.message_dialog(message)
		raise Exception(message)

	if sublime.platform() != 'windows':
		message = 'Sorry, at this point only Windows is supported.'
		sublime.message_dialog(message)
		raise Exception(message)

	SolutionSettings.loaded = True
	SolutionSettings.json = LoadSolutionSettings()

	# Organization
	SolutionSettings.resource_url = RetrieveSolutionSettings('organization_settings', 'resource_url')
	SolutionSettings.web_api_version = RetrieveSolutionSettings('organization_settings', 'web_api_version')
	SolutionSettings.azure_directory_name = RetrieveSolutionSettings('organization_settings', 'azure_directory_name')
	SolutionSettings.azure_tenant_id = RetrieveSolutionSettings('organization_settings', 'azure_tenant_id')
	SolutionSettings.web_api_url = SolutionSettings.resource_url + '/api/data/' + SolutionSettings.web_api_version

	# Preferences
	SolutionSettings.retrieve_managed_solutions = RetrieveSolutionSettings('preferences', 'retrieve_managed_solutions')
	SolutionSettings.retrieve_web_resource_types = RetrieveSolutionSettings('preferences', 'retrieve_web_resource_types')
	SolutionSettings.file_backup_folder = RetrieveSolutionSettings('preferences', 'file_backup_folder').strip('\\').strip('/')
	SolutionSettings.auto_open_browser_login = RetrieveSolutionSettings('preferences', 'auto_open_browser_login')

	# Temporary
	SolutionSettings.token_id = SolutionSettings.json['webresource_data']['o365token']

def RetrieveSolutionSettings(settingsType, settingsName = None, exitIfMissing = True):
	if settingsType in SolutionSettings.json:
		if settingsName == None:
			return SolutionSettings.json[settingsType]
		if settingsName in SolutionSettings.json[settingsType]:
			return SolutionSettings.json[settingsType][settingsName]
		else:
			if(exitIfMissing == True):
				message = 'Error - Could not find "' + settingsName + '" in settings file.'
				sublime.message_dialog(message)
				raise Exception(message)
	else:
		if(exitIfMissing == True):
			message = 'Error - Could not find "' + settingsType + '" in settings file.'
			sublime.message_dialog(message)
			raise Exception(message)
	return None

def CreateSettingsFile(path = ''):
	level = FindSettingsFile(path)['level']
	SolutionSettings.settings_path = path

	# Create New Settings File
	if level == -1:
		SolutionSettings.json = {}
	else:
		SolutionSettings.json = LoadSolutionSettings()

	if(RetrieveSolutionSettings('organization_settings', None, False) == None):
		SolutionSettings.json['organization_settings'] = {}
	if(RetrieveSolutionSettings('organization_settings', 'azure_directory_name', False) == None):
		SolutionSettings.json['organization_settings']['azure_directory_name'] = ''
	if(RetrieveSolutionSettings('organization_settings', 'azure_tenant_id', False) == None):
		SolutionSettings.json['organization_settings']['azure_tenant_id'] = ''
	if(RetrieveSolutionSettings('organization_settings', 'resource_url', False) == None):
		SolutionSettings.json['organization_settings']['resource_url'] = 'https://YOUR_ORGANIZATION_NAME.crmX.dynamics.com'
	if(RetrieveSolutionSettings('organization_settings', 'web_api_version', False) == None):
		SolutionSettings.json['organization_settings']['web_api_version'] = 'v9.1'
	if(RetrieveSolutionSettings('preferences', None, False) == None):
		SolutionSettings.json['preferences'] = {}
	if(RetrieveSolutionSettings('preferences', 'auto_open_browser_login', False) == None):
		SolutionSettings.json['preferences']['auto_open_browser_login'] = True
	if(RetrieveSolutionSettings('preferences', 'file_backup_folder', False) == None):
		SolutionSettings.json['preferences']['file_backup_folder'] = ''
	if(RetrieveSolutionSettings('preferences', 'retrieve_managed_solutions', False) == None):
		SolutionSettings.json['preferences']['retrieve_managed_solutions'] = False
	if(RetrieveSolutionSettings('preferences', 'retrieve_web_resource_types', False) == None):
		SolutionSettings.json['preferences']['retrieve_web_resource_types'] = '1,2,3,4,9,11,12'
	if(RetrieveSolutionSettings('webresource_data', None, False) == None):
		SolutionSettings.json['webresource_data'] = {}
	if(RetrieveSolutionSettings('webresource_data', 'files', False) == None):
		SolutionSettings.json['webresource_data']['files'] = {}
	if(RetrieveSolutionSettings('webresource_data', 'solutions', False) == None):
		SolutionSettings.json['webresource_data']['solutions'] = {}
	if(RetrieveSolutionSettings('webresource_data', 'o365token', False) == None):
		SolutionSettings.json['webresource_data']['o365token'] = ''

	SaveSolutionSettings(SolutionSettings.json)

def Run(action):
	print()

	LoadSettings()
	SolutionSettings.retry_once = True

	# Retrieve tenant id
	if(action == 'RetrieveTenantId') or (SolutionSettings.azure_directory_name != '' and SolutionSettings.azure_tenant_id == ''):
		if(RetrieveTenantId() == False):
			message = 'Could not find Tenant ID from Azure Directory name, try following:\n\n1. Find your Tenant ID from https://www.whatismytenantid.com.\n\nOR\n\n2. Open "portal.azure.com" > "Azure Active Directory" > "Properties" > "Directory ID".'
			sublime.message_dialog(message)
			raise Exception(message)

	# Get token
	if(SolutionSettings.token_id == None or SolutionSettings.token_id == ''):
		SolutionSettings.token_id = CreateToken()
	CreateRequestHeaders(SolutionSettings.token_id)

	# Test web connection
	try:
		query = '/webresourceset?fetchXml=\
			<fetch mapping="logical" count="500" version="1.0">\
				<entity name="webresource">\
					<all-attributes />\
					<filter type="and">\
						<condition attribute="systemuserid" operator="eq-userid" />\
					</filter>\
				</entity>\
			</fetch>'
		query_results = requests.get(SolutionSettings.web_api_url + query, headers=SolutionSettings.request_headers)
		req = requests.get(SolutionSettings.resource_url)
	except requests.exceptions.ConnectionError:
		message = 'Error - Could not connect to: ' + SolutionSettings.resource_url
		sublime.message_dialog(message)
		raise Exception(message)

	if(query_results.status_code == 401):
		CreateRequestHeaders(CreateToken())
		Run(action)
		return

	SolutionSettings.retry_once = True

	# Run action
	if(action == 'UploadWebResource'):
		UploadWebResource()
	elif(action == 'RetrieveSolutions'):
		RetrieveSolutions()
	elif(action == 'DownloadWebResources'):
		DownloadWebResources()

class UploadWebResourceSideBarCommand(sublime_plugin.WindowCommand):
	def run(self, files):
		SolutionSettings.selected_path = files[0]
		Run('UploadWebResource')
	def is_visible(self, files):
		if(len(files) == 0):
			return False
		settingsFile = FindSettingsFile(files[0])
		SolutionSettings.settings_path = settingsFile['path']
		SolutionSettings.settings_level = settingsFile['level']
		if(SolutionSettings.settings_level >= 2):
			return True
		return False

class CreateSettingsFileSideBarCommand(sublime_plugin.WindowCommand):
	def run(self, dirs):
		SolutionSettings.selected_path = dirs[0]
		CreateSettingsFile(dirs[0])
	def is_visible(self, dirs):
		if(len(dirs) == 0):
			return False
		settingsFile = FindSettingsFile(dirs[0])
		SolutionSettings.settings_path = settingsFile['path']
		SolutionSettings.settings_level = settingsFile['level']
		if(settingsFile['level'] == -1 or settingsFile['level'] == 0):
			return True
		return False

class RetrieveSolutionsSideBarCommand(sublime_plugin.WindowCommand):
	def run(self, dirs):
		SolutionSettings.selected_path = dirs[0]
		Run('RetrieveSolutions')
	def is_visible(self, dirs):
		if(len(dirs) == 0):
			return False
		settingsFile = FindSettingsFile(dirs[0])
		SolutionSettings.settings_path = settingsFile['path']
		SolutionSettings.settings_level = settingsFile['level']
		if(SolutionSettings.settings_level == 0):
			return True
		return False

class DownloadWebResourcesSideBarCommand(sublime_plugin.WindowCommand):
	def run(self, dirs):
		SolutionSettings.selected_path = dirs[0]
		Run('DownloadWebResources')
	def is_visible(self, dirs):
		if(len(dirs) == 0):
			return False
		settingsFile = FindSettingsFile(dirs[0])
		SolutionSettings.settings_path = settingsFile['path']
		SolutionSettings.settings_level = settingsFile['level']
		if(SolutionSettings.settings_level == 1):
			return True
		return False

class UploadWebResourceContextCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		# If window is not active on keymap
		if(self.view.file_name() == None):
			fileName = self.view.window().active_view().file_name()
		else:
			fileName = self.view.file_name()

		if(fileName == None):
			message = 'No file have been chosen.\n\nPlease choose a file to be uploaded.'
			sublime.message_dialog(message)
			raise Exception(message)

		SolutionSettings.selected_path = fileName
		settingsFile = FindSettingsFile(fileName)
		SolutionSettings.settings_path = settingsFile['path']

		# Autosave
		self.view.window().active_view().run_command('save')

		Run('UploadWebResource')

	def is_visible(self):
		settingsFile = FindSettingsFile(self.view.file_name())
		SolutionSettings.settings_path = settingsFile['path']
		SolutionSettings.settings_level = settingsFile['level']
		if(SolutionSettings.settings_level >= 2):
			return True
		return False

class RetrieveTenantIdSideBarCommand(sublime_plugin.WindowCommand):
	def un(self, dirs):
		SolutionSettings.selected_path = dirs[0]
		Run('RetrieveTenantId')
	def is_visible(self):
		return False

# Edit Web Resource
# https://...//main.aspx?id=...&etc=9333&pagetype=webresourceedit
