#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status

# 1. Configuration Variables
REPO_NAME="cmfit"
# Dynamically resolves the active folder if run inside the directory, or falls back to your home dir path
WORKSPACE_DIR="${1:-$HOME/$REPO_NAME}"

TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
COMMIT_MESSAGE="update: $TIMESTAMP"

echo "🎯 Set execution context to target workspace: $WORKSPACE_DIR"
mkdir -p "$WORKSPACE_DIR"
cd "$WORKSPACE_DIR"

# ----------------------------
# GENERATE DEFAULT .gitignore
# ----------------------------
if [ ! -f .gitignore ]; then
  echo "📄 Creating default .gitignore..."
  cat << 'EOF' > .gitignore
# Python artifacts
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Virtual environments
venv/
.venv/
env/

# Data & config files
*.json
!.json/
.env
.DS_Store
EOF
fi

# ----------------------------
# ENSURE REPO EXISTS LOCALLY
# ----------------------------
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "⚙️ Initializing new local Git repository..."
  git init
fi

# ----------------------------
# DETECT & SET BRANCH
# ----------------------------
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")

if [ "$CURRENT_BRANCH" = "HEAD" ]; then
  CURRENT_BRANCH="main"
  git checkout -b "$CURRENT_BRANCH"
fi

# Ensure branch name is main on new repositories
if [ "$CURRENT_BRANCH" = "master" ]; then
  git branch -m main
  CURRENT_BRANCH="main"
fi

# ----------------------------
# DETECT GITHUB AUTH & REMOTE
# ----------------------------
GH_USER=$(gh api user --jq '.login' 2>/dev/null || echo "")

if [ -z "$GH_USER" ]; then
  echo "❌ Error: You are not logged into the GitHub CLI (gh). Run 'gh auth login' first."
  exit 1
fi

DESIRED_URL="https://github.com/${GH_USER}/${REPO_NAME}.git"
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")

# Update/Add git remote
if [ "$REMOTE_URL" != "$DESIRED_URL" ]; then
  if [ -n "$REMOTE_URL" ]; then
    echo "🔄 Updating origin URL to $DESIRED_URL..."
    git remote set-url origin "$DESIRED_URL"
  else
    echo "➕ Adding remote origin: $DESIRED_URL"
    git remote add origin "$DESIRED_URL"
  fi
fi

# Create repository on GitHub if it doesn't exist
if ! gh repo view "${GH_USER}/${REPO_NAME}" >/dev/null 2>&1; then
  echo "🚀 Repository doesn't exist on GitHub. Creating '${GH_USER}/${REPO_NAME}'..."
  gh repo create "$REPO_NAME" --public --source=. || true
  echo "✅ Remote GitHub repository created."
fi

# ----------------------------
# STAGE & COMMIT
# ----------------------------
echo "📦 Staging files..."
git add .

if git diff --cached --quiet; then
  echo "ℹ️ No changes detected to commit."
else
  echo "📝 Committing: '$COMMIT_MESSAGE'"
  git commit -m "$COMMIT_MESSAGE"
fi

# ----------------------------
# PUSH TO GITHUB
# ----------------------------
UPSTREAM=$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo "")

if [ -z "$UPSTREAM" ]; then
  echo "🚀 Setting upstream and pushing to origin/$CURRENT_BRANCH..."
  git push -u origin "$CURRENT_BRANCH"
else
  echo "🚀 Pushing changes to $UPSTREAM..."
  git push
fi

echo "✅ Success! Code successfully pushed to https://github.com/${GH_USER}/${REPO_NAME}"