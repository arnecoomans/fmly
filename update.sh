#!/bin/bash
# Update script for Django applications
# Runs a git pull
# Based on the outcome it will activate the virtual environment, 
#  install new requirements, run migrations and collect static files
# Restarts the application with supervisorctl
#  based on the directory name (first part before the first dot)
# Author: Arne Coomans
# Version: 1.0.2

# Change to the script's directory
cd "$(dirname "$0")"

# Pull latest changes from Git
echo "Pulling latest changes from Git..."
git_output=$(git pull 2>&1)

# Check if git pull was successful
if [ $? -ne 0 ]; then
    echo "Error during git pull:"
    echo "$git_output"
    exit 1
fi

echo "Git pull complete."

# Check if there were any updates
if echo "$git_output" | grep -q 'Already up to date'; then
    echo "No changes detected. Exiting script."
    exit 0
fi

# Check if output contains 'migration' or 'project_static' or 'requirements.txt'
if echo "$git_output" | grep -q -e 'migration' -e 'static' -e 'requirements.txt'; then
    echo "Changes detected in requirements, migrations or static files. Activating virtual environment..."
    
    # Activate virtual environment in .venv directory in the current directory
    source .venv/bin/activate
    echo "Virtual environment activated."

    # Install any new requirements
    if echo "$git_output" | grep -q 'requirements.txt'; then
        echo "Installing new requirements..."
        python -m pip install --upgrade pip
        python -m pip install -r requirements.txt
        echo "Requirements installed."
    else
        echo "No changes in requirements detected. Skipping requirement installation."
    fi

    # Check for 'migration' keyword in git output
    if echo "$git_output" | grep -q 'migration'; then
        echo "Running migrations..."
        python manage.py migrate
        echo "Migrations complete."
    else
        echo "No changes in migrations detected. Skipping migration."
    fi
    
    # Check for 'project_static' keyword in git output
    if echo "$git_output" | grep -q 'static'; then
        echo "Collecting static files..."
        python manage.py collectstatic --noinput
        echo "Static files collected."
    else
        echo "No changes in static files detected. Skipping collectstatic."
    fi
else
    echo "No changes in migrations or static files detected. Skipping migration and collectstatic."
fi

# Check if there are any outdated packages
outdated=$(python -m pip list --outdated --format=freeze)

if [ -n "$outdated" ]; then
    echo "Outdated packages detected:"
    echo "$outdated"
    echo "Updating all packages from requirements.txt..."
    
    # Update all packages listed in requirements.txt
    python -m pip install --upgrade -r requirements.txt

    echo "All packages have been updated."
else
    echo "No outdated packages found."
fi

# Extract the first word from the current directory name, split by '.'
pool_name=$(basename "$PWD" | cut -d. -f1)

# Restart the application with supervisor using the extracted pool name
echo "Restarting application with supervisor for pool '$pool_name'..."
sudo supervisorctl restart "$pool_name"
echo "Application restart for pool '$pool_name' complete."