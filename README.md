# pyengine


## Introduction
A python framework to deploy and manage content in infrastructure as code format using YAML files 
on Windows, MacOSX, Linux


## Setup

### Via virtualenv
```
python3 -m virtualenv venv
source venv/bin/activate
python3 -m pip install -r ./src/equirements.txt
```

### Via docker
```
docker build -t pyengine:latest .

# Map the checks file inside the pyengine
docker run exec -v /opt/checks:/checks -v /opt/inputs:/inputs -it pyengine:latest /bin/bash
```

## Usage
```
# To execute all checks associated with YAML inputs specified in /inputs
python3 main.py -c /checks -i /inputs -r "check"
```