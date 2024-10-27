#!/bin/bash

# Change to the script's directory
cd "$(dirname "$0")"

# Pull latest changes from Git
echo "Pulling latest changes from Git..."
git_output=$(git pull)
echo "Git pull complete."

# Check if there were any updates
if echo "$git_output" | grep -q 'Already up to date'; then
    echo "No changes detected. Exiting script."
    exit 0
fi

# Check if output contains 'migration' or 'project_static'
if echo "$git_output" | grep -q -e 'migration' -e 'project_static'; then
    echo "Changes detected in migrations or static files. Activating virtual environment..."
    
    # Activate virtual environment in .venv directory in the current directory
    source .venv/bin/activate
    echo "Virtual environment activated."

    # Check for 'migration' keyword in git output
    if echo "$git_output" | grep -q 'migration'; then
        echo "Running migrations..."
        python manage.py migrate
        echo "Migrations complete."
    fi
    
    # Check for 'project_static' keyword in git output
    if echo "$git_output" | grep -q 'project_static'; then
        echo "Collecting static files..."
        python manage.py collectstatic --noinput
        echo "Static files collected."
    fi
else
    echo "No changes in migrations or static files detected. Skipping migration and collectstatic."
fi

# Restart the application with supervisor
echo "Restarting application with supervisor..."
sudo supervisorctl restart fmly
echo "Application restart complete."