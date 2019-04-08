# Algorithmic Platform for Nordnet nExtapi - APNn

The Algorithmic platform for Nordnet nExtAPI (APNn) is a trading platform that can be used to trade multiple assets on Nordnet’s nExtapi. It is developed to be flexible for change and is currently set to run in Nordnet’s development/test environment. The software is built so that it can easily be setup to work with the production environment as well.

This document aims to describe the software architecture and to briefly describe all the different functions and files being used. To get a deeper understanding, additional comments can be found in each of the different files.

Use this software at your own risk, and if you want to trade in the live Nordnet environment you will still need to certify yourself with your own implementation. This platform is built as an inspiration for future development. I’m not a professional developer and do not take any responsibility for the software not working.

Questions, requests, and suggestions can be sent to @ottovelander on twitter (checked sporadically).

## Installation

To setup APNn you will need to have python3 and pip3 installed

1. Installing modules
After downloading the APNn, install the modules in the “requirements.txt” file by running (you might need to install additional modules as well):
```
pip3 install –r requirements.txt
```

2. Certificates
Download your certificate files from nordnet. Download the “.pem”-file and put it in the lib folder (replacing the txt placeholder).

3. Config settings
Edit config.json by entering the location of your pem-file, add your login credentials to Nordnet, your e-mail information etc. More introduction to the config file is presented later.

4. Database
The asset history data collected by APNn is stored in a SQL database. APNn already comes with a created database for the test environment, but in order to create a new database (e.g. to trade different/multiple instruments) you will need to edit the “setup_database.py” and then create a new database by running
```
python3 setup_database.py
```

5. Start
To start APNn, run (from the main folder):
```
python3 main.py
```

## More details
More details how the software is structured can be found in "Introduction to APNn.pdf"
