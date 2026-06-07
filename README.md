# PineVision Collaboration Guide   
**A beginner‑friendly setup & workflow for team coding** 
## What is this guide for?   
You will learn how to:   - Install Git (the tool that tracks code changes)   - Download (clone) the PineVision project to your computer   - Get the latest work from your teammates before you start   - Save and upload your own changes to GitHub   - Work with branches to avoid breaking the main project   - Solve common problems like merge conflicts   --- 
## Step 1 – Install Git (only the first time) 
Git is the engine behind GitHub. You need it on your computer. 
1. Go to [https://git-scm.com/downloads](https://git-scm.com/downloads)   
2. Download the version for your operating system (Windows, macOS, Linux)   
3. Run the installer – all default settings are fine.   
4. **Verify the installation**   - Open **Command Prompt** (Windows) or **Terminal** (Mac/Linux)   - Type `git --version` and press Enter   - You should see something like `git version 2.xx.x`   
> **Tip:** If you use VS Code, Git is often recognised automatically. --- 
## Step 2 – Clone the repository (download the project) 
Cloning means you download the whole project to your computer for the first time. 
1. Open **Command Prompt** or **Terminal**   
2. Type this command and press Enter:   
```bash 
git clone https://github.com/geansiyams-sudo/PineVision.git 
``` 
3. After it finishes, move into the project folder:   
```bash 
cd PineVision 
``` 
> **Result:** You now have a copy of PineVision on your computer. You can open the 
folder in VS Code. --- 
## Step 3 – Open the project and work on it 
1. Open **VS Code**   
2. Click `File → Open Folder` and select the `PineVision` folder   
3. Edit files, run the project locally, and make your changes as usual   
> **Remember:** Your changes exist only on your computer for now. Later you will 
upload them. --- 
## Step 4 – Pull latest updates before you start coding 
Always get the newest work from your team **before** you change anything. This 
avoids conflicts. 
In the terminal (inside the `PineVision` folder), run:   
```bash 
git pull origin main 
``` 
Now your local project is the same as the latest version on GitHub. --- 
## Step 5 – Save and upload your changes (add, commit, push) 
When you have finished a piece of work and tested it, follow these steps to share it with 
the team. 
### 5.1 Check what has changed   
```bash 
git status 
``` 
You will see a list of files you modified or added. 
### 5.2 Stage the changes (prepare them for saving)   
```bash 
git add . 
``` 
The dot `.` means “all changed files”. You can also add individual files with `git add 
filename`. 
### 5.3 Commit (create a snapshot with a message)   
```bash 
git commit -m "Describe what you changed – e.g. Fixed login button" 
``` 
The message must be short but clear. 
### 5.4 Push (upload your commits to GitHub)   
```bash 
git push origin main 
``` 
Now your work is visible to the whole team on GitHub. --- 
## Step 6 – Best practices (make teamwork smooth) 
| Do this … | Because … | 
|-----------|------------| 
| `git pull origin main` **every time** before you start coding | You avoid working on an 
old version | 
| Write meaningful commit messages | Teammates understand what you did | 
| `git add .` after testing your code | You don’t forget new files | 
| Push at least once a day | Others can see your progress | 
**Example of a good commit message:**   
`git commit -m "Added password reset feature and fixed typo in header"` 
**Bad commit message:** `git commit -m "update"` – don’t do that. --- 
## Step 7 – Branch workflow (recommended for teams) 
Instead of working directly on `main`, you create a **branch** – a separate copy for your 
feature or fix. Then you merge it via a **Pull Request**. This keeps `main` always 
stable. 
### 7.1 Create and switch to a new branch   
```bash 
git checkout -b feature-name 
``` 
Replace `feature-name` with something short, like `add-login` or `fix-bug-12`. 
### 7.2 Work normally (edit, add, commit – as in Step 5)   
Push the branch to GitHub:   
```bash 
git push origin feature-name 
``` 
### 7.3 Open a Pull Request on GitHub   - Go to the repository page on GitHub   - You will see a banner “feature-name had recent pushes” – click **Compare & pull 
request**   - Add a description and create the pull request   - Ask a teammate to review and merge it 
### 7.4 After merging, switch back to `main` and pull   
```bash 
git checkout main 
git pull origin main 
``` 
> **Why branches are great:** You can try new things without breaking the working 
code. Several people can work on different features at the same time. --- 
## Step 8 – Common issues and solutions 
| Issue | What it means | Solution | 
|-------|---------------|----------| 
| `Repository not found` | Wrong URL or you don’t have access | Check the URL: 
`https://github.com/geansiyams-sudo/PineVision.git` – ask the owner for permission. | 
| `Authentication failed` | GitHub does not recognise you | Use a **personal access 
token** (instead of a password). [GitHub 
guide](https://docs.github.com/en/authentication/keeping-your-account-and-data
secure/managing-your-personal-access-tokens) | 
| `Merge conflict` | Two people changed the same lines | Git will mark the conflicted file. 
Open it, search for `<<<<<<<`, decide what to keep, remove the markers, then `git add 
.` and `git commit`. | 
| `! [rejected] main -> main (fetch first)` | You forgot to pull before pushing | Run `git pull 
origin main`, fix any conflicts, then push again. | --- 
## Quick cheat sheet (summary for daily work) 
```bash 
# Start of your work session 
git pull origin main 
# After you finish coding 
git status 
git add . 
git commit -m "Explain your changes" 
git push origin main 
``` 
If you use branches:   
```bash 
git checkout -b new-feature 
# … work, add, commit … 
git push origin new-feature 
# Then create Pull Request on GitHub 
``` --- 
## Need more help? - [GitHub’s own beginner guide](https://docs.github.com/en/get-started)   - [VS Code + Git integration](https://code.visualstudio.com/docs/sourcecontrol/overview)   - Ask your team or open an issue on the GitHub repository. --- 
**Now you are ready to collaborate on PineVision like a pro!        --- 
