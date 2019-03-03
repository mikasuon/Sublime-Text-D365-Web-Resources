# Sublime Text D365 Web Resources

Sublime Text D365 Web Resources was driven by the need to improve productivity of Dynamics 365 Web Resources.

This Sublime Text plugin was built with speed and security in mind, the main aspect was to be able to edit Dynamics 365 Web Resources with a fast and feature packed text editor (Sublime Text 3.X).

Features:
  * Create local files from Dynamics D365 Web Resources. Supports file hierarchies when a Web Resource have been named eg. "prefix_/project/filename.js".
  * Uses Microsoft Azure Active Directory ADAL libraries (https://github.com/AzureAD/azure-activedirectory-library-for-python). Supports Multi-factor Authentication (MFA). No passwords ever saved to config files!
  * It is possible to connect to multiple organizations at the same time. Source code can be easily copy/pasted between organizations.
  * Automatic file backups when uploading Web Resources.
  * Automatic version conflict detection. User will be warned if a Web Resource have been modified since Web Resources were downloaded last time (of course local and server backups will be taken if user makes a wrong decision).
