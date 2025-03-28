import os
import re
import json
import datetime
import subprocess
import time
import logging
import sys
from pathlib import Path
import shutil
import requests
from typing import List, Dict, Optional

# Set up logging with rotation
# Get the absolute path for the log file
current_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(current_dir, "daily_journal_manager.log")

# Import the rotating file handler
from logging.handlers import RotatingFileHandler

# Create a rotating file handler for automatic log rotation
rotating_handler = RotatingFileHandler(
    log_file,
    maxBytes=5 * 1024 * 1024,  # 5 MB max file size
    backupCount=5,             # Keep 5 backup files (daily_journal_manager.log.1, .2, etc.)
    encoding='utf-8'           # Ensure proper encoding for any unicode characters
)

# Set formatter for both handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
rotating_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        rotating_handler,    # Rotating file handler for log rotation
        console_handler      # Console handler for terminal output
    ]
)
logger = logging.getLogger(__name__)

class DailyJournalManager:
    """Main class to manage daily journal operations."""
    
    def __init__(self, config_path: str = "config-file.json"):
        """Initialize with configuration."""
        self.config = self._load_config(config_path)
        self.today = datetime.datetime.now().strftime("%Y-%m-%d")
        self.yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        self.obsidian_dir = Path(self.config.get("obsidian_dir", ""))
        self.template_path = Path(self.config.get("template_path", ""))
        self.today_file = self.obsidian_dir / f"{self.today}.md"
        self.yesterday_file = self.obsidian_dir / f"{self.yesterday}.md"
        
        # Find the most recent journal entry date
        self.last_entry_date, self.days_since_last_entry = self._find_last_journal_entry()
        self.last_entry_file = self.obsidian_dir / f"{self.last_entry_date}.md" if self.last_entry_date else None
        
        # Initialize integrations
        self.git = GitIntegration(self.obsidian_dir) if self.config.get("use_git", False) else None
        self.llm = LocalLLMIntegration(
            self.config.get("llm_endpoint", "http://localhost:11434/api/generate"),
            self.config.get("llm_model", "llama3.2")
        )
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config file {config_path} not found, creating with defaults")
            default_config = {
                "obsidian_dir": str(Path.home() / "Documents" / "Obsidian" / "Daily"),
                "template_path": str(Path.home() / "Documents" / "Obsidian" / "Templates" / "Daily Template.md"),
                "use_git": False,
                "llm_endpoint": "http://localhost:11434/api/generate",
                "llm_model": "llama3.2",
                "use_7day_summary": True,
                "use_30day_summary": True,
                "summary_prompt_7": "Summarize the main themes, trajectory, and insights from the past 7 days of journal entries in three sentences.",
                "summary_prompt_30": "Summarize the main themes, trajectory, and insights from the past 30 days of journal entries in three sentences.",
                "run_limitless_sync": True,
                "limitless_api_key": "",
                "limitless_save_dir": "",  # Default empty, will use script's directory
                "limitless_backup_dir": ""  # Secondary location for data backup
            }
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=4)
            return default_config
            
    def _find_last_journal_entry(self) -> tuple:
        """Find the most recent journal entry before today.
        
        Returns:
            tuple: (last_entry_date, days_since_last_entry)
        """
        try:
            today_date = datetime.datetime.now().date()
            
            # List all markdown files in the Obsidian directory
            if not self.obsidian_dir.exists():
                logger.error(f"Obsidian directory not found: {self.obsidian_dir}")
                return None, None
                
            # Get all markdown files
            md_files = list(self.obsidian_dir.glob("*.md"))
            
            # Filter out today's file and extract dates
            entry_dates = []
            for file_path in md_files:
                try:
                    # Get the filename without extension as a potential date
                    date_str = file_path.stem
                    entry_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                    
                    # Only include dates before today
                    if entry_date < today_date:
                        entry_dates.append(entry_date)
                except ValueError:
                    # Filename is not in date format, skip
                    continue
            
            if not entry_dates:
                logger.warning("No previous journal entries found")
                return None, None
                
            # Find the most recent date
            last_date = max(entry_dates)
            last_date_str = last_date.strftime("%Y-%m-%d")
            
            # Calculate days since last entry
            days_since = (today_date - last_date).days
            
            logger.info(f"Found last journal entry: {last_date_str}, {days_since} days ago")
            return last_date_str, days_since
            
        except Exception as e:
            logger.error(f"Error finding last journal entry: {e}")
            return None, None
    
    def run_daily_carryover(self):
        """Execute the daily carryover process."""
        logger.info(f"Starting daily carryover for {self.today}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info(f"Obsidian directory: {self.obsidian_dir}")
        logger.info(f"Template path: {self.template_path}")
        logger.info(f"Absolute path to today's file: {os.path.abspath(self.today_file)}")
        
        # Verify template path exists before proceeding
        if not self.template_path.exists():
            logger.error(f"Template file not found at {self.template_path}. Aborting.")
            return False
            
        # Verify Obsidian directory exists
        if not self.obsidian_dir.exists():
            logger.error(f"Obsidian directory not found at {self.obsidian_dir}. Aborting.")
            return False
            
        # 1. Create today's file if it doesn't exist
        created = self.create_todays_file()
        
        # Only proceed if today's file exists or was successfully created
        if not created and not self.today_file.exists():
            logger.error(f"Failed to create today's file and it doesn't exist. Aborting daily carryover.")
            return False
            
        # 2. Add yesterday's note reference
        self.add_yesterday_reference()
        
        # 3. Ensure the "Due in the next two weeks" header exists with proper formatting
        self.ensure_anticipation_header()
        
        # 4. Carry over incomplete tasks from the last entry
        self.carryover_incomplete_tasks()
        
        # 5. Generate and update summaries if enabled
        if self.config.get("use_7day_summary", True) or self.config.get("use_30day_summary", True):
            self.update_summaries()
        
        # 6. Add modification timestamp
        self.add_modification_timestamp()
        
        # 7. Run Limitless sync script if enabled
        if self.config.get("run_limitless_sync", False):
            self.run_limitless_sync()
        
        # 8. Commit changes if git integration is enabled
        if self.git:
            self.git.commit_changes(f"Daily carryover for {self.today}")
        
        logger.info("Daily carryover completed successfully")
        return True
    
    def create_todays_file(self):
        """Create today's file from template if it doesn't exist.
        
        Returns:
            bool: True if file was created or already exists, False if failed
        """
        # If file already exists, nothing to do
        if self.today_file.exists():
            logger.info(f"Today's file already exists: {self.today_file}")
            return True
            
        # Template validation
        if not self.template_path.exists():
            logger.error(f"Template file {self.template_path} not found")
            # Check if template path seems valid but might have case sensitivity issues
            template_dir = self.template_path.parent
            if template_dir.exists():
                logger.info(f"Looking for template file in: {template_dir}")
                for file in template_dir.iterdir():
                    logger.info(f"Found file: {file.name}")
            return False
        
        # Parent directory check and creation    
        try:
            # Ensure parent directory exists
            parent_dir = self.today_file.parent
            if not parent_dir.exists():
                logger.info(f"Creating parent directory: {parent_dir}")
                parent_dir.mkdir(parents=True, exist_ok=True)
                
            # Log template details
            logger.info(f"Template file size: {self.template_path.stat().st_size} bytes")
            
            # Copy the template
            shutil.copy(self.template_path, self.today_file)
            
            # Verify the file was created
            if self.today_file.exists():
                logger.info(f"Successfully created today's file from template: {self.today_file}")
                logger.info(f"New file size: {self.today_file.stat().st_size} bytes")
                
                # Add to git if enabled
                if self.git:
                    self.git.add_file(self.today_file)
                    self.git.commit_changes(f"Created new daily note for {self.today}")
                return True
            else:
                logger.error(f"File creation appeared to succeed but file does not exist: {self.today_file}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating today's file: {e}")
            # Try to log more details about the error
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def add_yesterday_reference(self):
        """Add reference to the previous journal entry based on when it was created."""
        # Verify today's file exists
        if not self.today_file.exists():
            logger.warning("Today's file doesn't exist, skipping previous entry reference")
            return False
            
        # Skip if we couldn't determine the last entry date
        if not self.last_entry_date:
            logger.warning("No previous journal entries found, skipping reference")
            return True
            
        # Create appropriate reference message based on the gap
        if self.days_since_last_entry == 1:
            # Yesterday's entry exists, use normal reference
            reference_note = f"\n\n Yesterday's note: [[{self.yesterday}]]"
        else:
            # Gap detected, create a custom message
            reference_note = f"\n\n The last journal entry was [[{self.last_entry_date}]], which was {self.days_since_last_entry} days ago"
            logger.info(f"Detected a {self.days_since_last_entry}-day gap since last journal entry")
        
        try:
            file_content = self.today_file.read_text(encoding='utf-8')
            
            # Check if any reference already exists (both possible formats)
            yesterday_ref = f" Yesterday's note: [[{self.yesterday}]]"
            last_entry_ref = f" The last journal entry was [[{self.last_entry_date}]]"
            
            if yesterday_ref not in file_content and last_entry_ref not in file_content:
                # Find the "## Life" section
                life_pattern = r'(## Life.*?)(\n\n|\n(?=##)|$)'
                match = re.search(life_pattern, file_content, re.DOTALL)
                
                if match:
                    # Get the content before and after the Life section
                    life_section = match.group(1)
                    section_end = match.group(2)
                    
                    # Insert the reference note after the Life heading
                    new_section = f"{life_section}\n{reference_note}{section_end}"
                    updated_content = file_content.replace(match.group(0), new_section)
                    
                    with open(self.today_file, 'w', encoding='utf-8') as f:
                        f.write(updated_content)
                    logger.info(f"Added previous entry reference after Life section: {reference_note}")
                else:
                    logger.warning("## Life section not found, appending to end of file")
                    with open(self.today_file, 'a', encoding='utf-8') as f:
                        f.write(f"\n{reference_note}\n")
                
                if self.git:
                    self.git.add_file(self.today_file)
            else:
                logger.info("Previous entry reference already exists")
                
            return True
                
        except Exception as e:
            logger.error(f"Error adding previous entry reference: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def ensure_anticipation_header(self):
        """Ensure the anticipation header exists with proper formatting."""
        header = "Due in the next two weeks - Anticipation"
        
        # Verify today's file exists
        if not self.today_file.exists():
            logger.warning("Today's file doesn't exist, skipping header check")
            return False
        
        try:
            file_content = self.today_file.read_text(encoding='utf-8')
            
            if header not in file_content:
                with open(self.today_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n## {header}\n\n")
                logger.info(f"Added anticipation header: {header}")
                
                if self.git:
                    self.git.add_file(self.today_file)
            else:
                # Ensure proper formatting (two newlines after header)
                pattern = rf"(## {header}.*?)(\n\n|$)"
                match = re.search(pattern, file_content, re.DOTALL)
                
                if match:
                    current_header = match.group(1)
                    # Ensure the header is followed by two newlines
                    if not current_header.endswith('\n\n'):
                        new_header = current_header
                        if new_header.endswith('\n'):
                            new_header += '\n'
                        else:
                            new_header += '\n\n'
                        
                        updated_content = file_content.replace(current_header, new_header)
                        with open(self.today_file, 'w', encoding='utf-8') as f:
                            f.write(updated_content)
                        
                        logger.info(f"Reformatted anticipation header")
                        
                        if self.git:
                            self.git.add_file(self.today_file)
                            
            return True
                            
        except Exception as e:
            logger.error(f"Error ensuring anticipation header: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def carryover_incomplete_tasks(self):
        """Carry over incomplete tasks from the last journal entry."""
        # Verify today's file exists
        if not self.today_file.exists():
            logger.warning("Today's file doesn't exist, skipping task carryover")
            return False
        
        # Use last entry file if it exists, otherwise fallback to yesterday's file (for backwards compatibility)
        source_file = self.last_entry_file if self.last_entry_file else self.yesterday_file
        source_date = self.last_entry_date if self.last_entry_date else self.yesterday
        
        if not source_file or not source_file.exists():
            logger.warning(f"Last entry file not found: {source_file}")
            return True  # Not a fatal error, just nothing to carry over
        
        try:
            # Read the content of the last entry
            last_entry_content = source_file.read_text(encoding='utf-8')
            
            # Find incomplete tasks in the anticipation section
            incomplete_tasks = []
            in_anticipation_section = False
            
            for line in last_entry_content.split('\n'):
                if re.search(r'##.*Due in the next two weeks - Anticipation', line):
                    in_anticipation_section = True
                    continue
                
                if in_anticipation_section and line.startswith('## '):
                    in_anticipation_section = False
                    continue
                
                if in_anticipation_section and line.strip().startswith('- [ ]'):
                    incomplete_tasks.append(line)
            
            if not incomplete_tasks:
                logger.info(f"No incomplete tasks found in the last entry ({source_date}).")
                return True
                
            today_content = self.today_file.read_text(encoding='utf-8')
            
            # Find the anticipation section in today's file
            match = re.search(r'(##.*Due in the next two weeks - Anticipation.*?)(?=\n##|\Z)', 
                             today_content, re.DOTALL)
            
            if not match:
                logger.warning("Anticipation header not found in today's file.")
                return False
            
            # Get current anticipation section
            anticipation_section = match.group(1)
            new_anticipation_section = anticipation_section
            tasks_added = False
            
            # If there's a gap of more than 1 day, add a note about where these tasks came from
            gap_note = ""
            if self.days_since_last_entry > 1:
                gap_note = f"\n<!-- Tasks carried over from {source_date}, {self.days_since_last_entry} days ago -->\n"
                new_anticipation_section += gap_note
                tasks_added = True
            
            for task in incomplete_tasks:
                if task not in today_content:
                    if new_anticipation_section.endswith('\n\n'):
                        new_anticipation_section += task
                    elif new_anticipation_section.endswith('\n'):
                        new_anticipation_section += task
                    else:
                        new_anticipation_section += '\n' + task
                    
                    logger.info(f"Added task: {task}")
                    tasks_added = True
            
            if tasks_added:
                # Replace anticipation section with new content
                updated_content = today_content.replace(anticipation_section, new_anticipation_section)
                
                with open(self.today_file, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
                
                logger.info(f"Carried over {len(incomplete_tasks)} tasks from {source_date}")
                
                if self.git:
                    self.git.add_file(self.today_file)
                    self.git.commit_changes(f"Carried over incomplete tasks for {self.today}")
            else:
                logger.info("All tasks already present in today's file")
                
            return True
            
        except Exception as e:
            logger.error(f"Error carrying over incomplete tasks: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def update_summaries(self):
        """Generate and update summaries using LLM."""
        # Verify today's file exists
        if not self.today_file.exists():
            logger.warning("Today's file doesn't exist, skipping summary updates")
            return False
            
        try:
            summaries_updated = False
            
            # Get summary for past 7 days if enabled
            if self.config.get("use_7day_summary", True):
                seven_day_input = self._collect_past_entries(7)
                summary_7 = self.llm.generate_summary(
                    self.config.get("summary_prompt_7", "Summarize the past 7 days"),
                    seven_day_input
                )
                success = self._update_summary_section("## 7-Day Summary", summary_7)
                if success:
                    logger.info("Updated 7-day summary")
                    summaries_updated = True
                else:
                    logger.warning("Failed to update 7-day summary")

            # Get summary for past 30 days if enabled
            if self.config.get("use_30day_summary", True):
                thirty_day_input = self._collect_past_entries(30)
                summary_30 = self.llm.generate_summary(
                    self.config.get("summary_prompt_30", "Summarize the past 30 days"),
                    thirty_day_input
                )
                success = self._update_summary_section("## 30-Day Summary", summary_30)
                if success:
                    logger.info("Updated 30-day summary")
                    summaries_updated = True
                else:
                    logger.warning("Failed to update 30-day summary")

            # Commit the changes if any summaries were updated
            if summaries_updated and self.git:
                self.git.add_file(self.today_file)
                self.git.commit_changes(f"Updated summaries for {self.today}")
                
            return True
                
        except Exception as e:
            logger.error(f"Error updating summaries: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _collect_past_entries(self, days: int) -> str:
        """Collect past journal entries for specified number of days."""
        combined_entries = ""
        
        for i in range(1, days + 1):
            date = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            file_path = self.obsidian_dir / f"{date}.md"
            
            if file_path.exists():
                logger.info(f"Adding {date} to {days}-day summary input")
                content = file_path.read_text(encoding='utf-8')
                combined_entries += f"\n\n### {date}\n\n{content}\n\n"
            else:
                logger.info(f"Note for {date} not found, skipping")
        
        return combined_entries
    
    def _update_summary_section(self, heading: str, new_summary: str) -> bool:
        """Update or append a summary section in today's file.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.today_file.exists():
            logger.warning("Today's file doesn't exist, skipping summary update")
            return False
            
        try:
            content = self.today_file.read_text(encoding='utf-8')
            
            # Check if heading exists
            if heading in content:
                # Replace existing summary
                pattern = rf"({heading}\n).*?(?=\n##|\Z)"
                updated_content = re.sub(pattern, f"\\1{new_summary}\n", content, flags=re.DOTALL)
            else:
                # Append new summary section
                updated_content = content + f"\n\n{heading}\n{new_summary}\n"
            
            with open(self.today_file, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            
            logger.info(f"Updated {heading}")
            return True
        
        except Exception as e:
            logger.error(f"Error updating summary section: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def add_modification_timestamp(self):
        """Add or update modification timestamp.
        
        Returns:
            bool: True if successful, False otherwise
        """
        timestamp = f"<small>Last modified: {datetime.datetime.now()}</small>"
        
        # Verify today's file exists
        if not self.today_file.exists():
            logger.warning("Today's file doesn't exist, skipping timestamp")
            return False
            
        try:
            content = self.today_file.read_text(encoding='utf-8')
            
            # Remove any existing timestamp
            content = re.sub(r'<small>Last modified:.*?</small>', '', content)
            
            # Add new timestamp
            content += f"\n\n{timestamp}"
            
            with open(self.today_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info("Added modification timestamp")
            
            if self.git:
                self.git.add_file(self.today_file)
                
            return True
        
        except Exception as e:
            logger.error(f"Error adding modification timestamp: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
            
    def run_limitless_sync(self):
        """Run the Limitless sync script from the grimoire/lifelog directory.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get the path to the lifelog sync script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            repo_root = os.path.dirname(script_dir)  # Go up one level to get repository root
            lifelog_script = os.path.join(repo_root, "grimoire", "lifelog", "limitless_sync.py")
            
            # Check if the script exists
            if not os.path.exists(lifelog_script):
                logger.error(f"Limitless sync script not found at {lifelog_script}")
                return False
                
            logger.info(f"Running Limitless sync script: {lifelog_script}")
            
            # Get the API key from config or environment
            api_key = self.config.get("limitless_api_key", os.environ.get("LIMITLESS_API_KEY", ""))
            
            if not api_key:
                logger.warning("No Limitless API key provided in config or environment, script may prompt for it")
            
            # Prepare environment variables for the subprocess
            env = os.environ.copy()
            
            # Set custom save directory if configured
            save_dir = self.config.get("limitless_save_dir", "")
            if save_dir:
                logger.info(f"Using custom limitless save directory: {save_dir}")
                env["LIMITLESS_SAVE_DIR"] = save_dir
                
            # Set backup directory if configured
            backup_dir = self.config.get("limitless_backup_dir", "")
            if backup_dir:
                logger.info(f"Using limitless backup directory: {backup_dir}")
                env["LIMITLESS_BACKUP_DIR"] = backup_dir
                
            # Handle timezone configuration
            timezone = self.config.get("limitless_timezone", "America/New_York")
            auto_detect = self.config.get("auto_detect_timezone", True)
            
            # Check system timezone if auto-detection is enabled
            if auto_detect:
                try:
                    import tzlocal
                    system_timezone = tzlocal.get_localzone_name()
                    if system_timezone != timezone:
                        logger.warning(f"System timezone ({system_timezone}) differs from configured timezone ({timezone})")
                        logger.info(f"Using system timezone: {system_timezone}")
                        timezone = system_timezone
                        # Update the config file with the new timezone
                        self.config["limitless_timezone"] = system_timezone
                        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config-file.json"), 'w') as f:
                            json.dump(self.config, f, indent=2)
                        logger.info(f"Updated config file with new timezone: {system_timezone}")
                except ImportError:
                    logger.warning("tzlocal package not available. Install with 'pip install tzlocal' for automatic timezone detection")
            
            # Set the timezone for Limitless sync
            logger.info(f"Using timezone for Limitless sync: {timezone}")
            env["LIMITLESS_TIMEZONE"] = timezone
            
            # Run the script
            cmd = [sys.executable, lifelog_script]
            if api_key:
                cmd.append(api_key)
                
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,  # Don't raise an exception on non-zero exit
                env=env  # Pass the environment variables
            )
            
            if result.returncode == 0:
                logger.info("Limitless sync completed successfully")
                logger.debug(f"Limitless sync output: {result.stdout}")
                return True
            else:
                logger.error(f"Limitless sync failed with return code {result.returncode}")
                logger.error(f"Limitless sync stderr: {result.stderr}")
                logger.error(f"Limitless sync stdout: {result.stdout}")
                return False
                
        except Exception as e:
            logger.error(f"Error running Limitless sync: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False


class GitIntegration:
    """Class to handle Git integration for version control."""
    
    def __init__(self, repo_path: Path):
        """Initialize with repository path."""
        self.repo_path = repo_path
        self._ensure_git_repo()
    
    def _ensure_git_repo(self):
        """Ensure the directory is a Git repository."""
        if not (self.repo_path / ".git").exists():
            try:
                # Initialize git repository if it doesn't exist
                result = subprocess.run(
                    ["git", "init"],
                    cwd=self.repo_path,
                    check=True,
                    capture_output=True,
                    text=True
                )
                logger.info(f"Initialized git repository: {result.stdout.strip()}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to initialize git repository: {e.stderr}")
    
    def add_file(self, file_path: Path):
        """Add a file to git staging area."""
        try:
            result = subprocess.run(
                ["git", "add", str(file_path)],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"Added file to git: {file_path.name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to add file to git: {e.stderr}")
            return False
    
    def commit_changes(self, message: str):
        """Commit staged changes with provided message."""
        try:
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"Committed changes: {result.stdout.strip()}")
            return True
        except subprocess.CalledProcessError as e:
            if "nothing to commit" in e.stderr:
                logger.info("No changes to commit")
                return True
            else:
                logger.error(f"Failed to commit changes: {e.stderr}")
                return False
    
    def get_diff(self, file_path: Path) -> str:
        """Get git diff for a specific file."""
        try:
            result = subprocess.run(
                ["git", "diff", "--", str(file_path)],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get diff: {e.stderr}")
            return ""
    
    def log_changes(self, file_path: Path, num_entries: int = 5) -> List[Dict[str, str]]:
        """Get recent commit history for a specific file."""
        try:
            result = subprocess.run(
                ["git", "log", f"-{num_entries}", "--pretty=format:%h|%an|%ad|%s", "--", str(file_path)],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True
            )
            
            logs = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split('|')
                    if len(parts) >= 4:
                        logs.append({
                            "hash": parts[0],
                            "author": parts[1],
                            "date": parts[2],
                            "message": parts[3]
                        })
            
            return logs
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get commit history: {e.stderr}")
            return []


class LocalLLMIntegration:
    """Class to handle interactions with local language models."""
    
    def __init__(self, endpoint: str, model: str):
        """Initialize with LLM API endpoint and model name."""
        self.endpoint = endpoint
        self.model = model
    
    def generate_summary(self, prompt: str, input_text: str) -> str:
        """Generate a summary using the local LLM."""
        try:
            full_prompt = f"{prompt}\n\n{input_text}"
            
            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": False
            }
            
            response = requests.post(self.endpoint, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                summary = result.get("response", "No summary generated.")
                logger.info("Successfully generated summary")
                return summary
            else:
                logger.error(f"Failed to generate summary: {response.status_code} - {response.text}")
                return "Failed to generate summary."
        
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return "Error generating summary."


class SchedulerIntegration:
    """Class to handle scheduling script execution in Windows."""
    
    @staticmethod
    def create_daily_task(script_path: str, task_name: str, start_time: str):
        """Create a Windows scheduled task to run the script daily."""
        try:
            # Get the full path to the Python interpreter
            python_path = sys.executable
            # Replace 'python.exe' with 'pythonw.exe' if needed
            pythonw_path = python_path.replace('python.exe', 'pythonw.exe')
            
            # Format the command with proper quoting and full paths
            cmd = [
                "schtasks", "/create", "/tn", task_name,
                "/tr", f'"{pythonw_path}" "{script_path}"',
                "/sc", "daily",
                "/st", start_time,
                "/f"  # Force (overwrites existing task)
            ]
            
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            
            logger.info(f"Created scheduled task: {result.stdout.strip()}")
            return True
        
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create scheduled task: {e.stderr}")
            return False
    
    @staticmethod
    def create_startup_task(script_path: str, task_name: str, delay_minutes: int = 5):
        """Create a Windows task that runs at startup with delay."""
        try:
            # Create a batch file that introduces delay and then runs the script
            batch_path = Path(script_path).parent / "run_with_delay.bat"
            with open(batch_path, 'w') as f:
                f.write(f"@echo off\n")
                f.write(f"timeout /t {delay_minutes * 60} /nobreak\n")  # delay in seconds
                f.write(f'pythonw "{script_path}"\n')
            
            # Create startup shortcut in Windows startup folder
            startup_folder = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            shortcut_path = startup_folder / f"{task_name}.bat"
            
            # Copy the batch file to the startup folder
            shutil.copy(batch_path, shortcut_path)
            
            logger.info(f"Created startup task: {shortcut_path}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to create startup task: {e}")
            return False


def main():
    """Main entry point for the script."""
    try:
        # Ensure we're using the correct working directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        logger.info(f"🔄 MANUAL RUN: Set working directory to: {os.getcwd()}")
        
        # Use explicit config path relative to the script
        config_path = os.path.join(script_dir, "config-file.json")
        logger.info(f"🔄 MANUAL RUN: Using config file: {config_path}")
        
        # Initialize and run the daily journal manager
        manager = DailyJournalManager(config_path=config_path)
        success = manager.run_daily_carryover()
        
        if success:
            logger.info("🔄 MANUAL RUN: Daily journal manager completed successfully")
        else:
            logger.error("🔄 MANUAL RUN: Daily journal manager failed - see log for details")
            print("\nDaily journal operation failed - check the log file for details")
            print(f"Log file: {log_file}")
        
        # For Windows Task Scheduler integration
        # current_script = os.path.abspath(__file__)
        # SchedulerIntegration.create_daily_task(current_script, "DailyJournalManager", "08:00")
        # SchedulerIntegration.create_startup_task(current_script, "DailyJournalManagerStartup", 5)
    
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        print(f"\nError: {e}")
        print(f"Check the log file for details: {log_file}")


def scheduled_main():
    """Entry point for scheduled execution using the APScheduler package."""
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

    def job():
        logger.info("⏰ SCHEDULED RUN: Running via APScheduler at " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        try:
            # Use the full path to the config file when running as a scheduled job
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config-file.json")
            logger.info(f"Using config file: {config_path}")
            
            # Set the working directory to the script's directory to ensure proper paths
            script_dir = os.path.dirname(os.path.abspath(__file__))
            os.chdir(script_dir)
            logger.info(f"Changed working directory to: {os.getcwd()}")
            
            manager = DailyJournalManager(config_path=config_path)
            success = manager.run_daily_carryover()
            
            if success:
                logger.info("⏰ SCHEDULED RUN: Completed successfully")
            else:
                logger.error("⏰ SCHEDULED RUN: Failed to create/update journal entry")
                
        except Exception as e:
            logger.error(f"Error in scheduled job: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    def job_listener(event):
        if event.exception:
            logger.error(f"⏰ SCHEDULED RUN: Job failed: {event.exception}")
        else:
            logger.info(f"⏰ SCHEDULED RUN: Job executed successfully at {datetime.datetime.now()}")
            
            # Record when the job was actually executed versus when it was scheduled
            scheduled_time = event.scheduled_run_time
            actual_time = datetime.datetime.now()
            delay = actual_time - scheduled_time
            
            # Log the delay information for monitoring
            if delay.total_seconds() > 300:  # More than 5 minutes delay
                logger.warning(f"⏰ SCHEDULED RUN: Executed {int(delay.total_seconds()//60)} minutes late")
            else:
                logger.info(f"⏰ SCHEDULED RUN: Executed on time (delay: {int(delay.total_seconds())} seconds)")

    # Create a background scheduler that will properly handle missed jobs
    scheduler = BackgroundScheduler(
        job_defaults={
            'coalesce': True,  # Combine multiple missed runs into one
            'max_instances': 1,  # Don't run the same job concurrently
            'misfire_grace_time': 15*60  # Allow missed jobs up to 15 mins late
        }
    )
    
    # Schedule job to run at 8:00 AM
    scheduler.add_job(
        job, 
        trigger=CronTrigger(hour=8, minute=0),
        id='daily_carryover',
        name='Daily Journal Carryover'
    )
    
    # Add listener for job events
    scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    
    # Start the scheduler in the background
    scheduler.start()
    logger.info("APScheduler started - Daily job scheduled to run at 08:00")
    
    return scheduler  # Return for reference by main program


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--scheduled":
        # Start scheduler in background
        scheduler = scheduled_main()
        
        try:
            # Keep the script alive but let it run in background by sleeping
            # This allows it to be run as a service or with pythonw without keeping a terminal open
            import time
            
            # Log that we're about to go into background mode
            logger.info("Script running in background mode, press Ctrl+C to exit")
            
            # Keep script alive but don't use 100% CPU
            while True:
                time.sleep(3600)  # Sleep for an hour
        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            logger.info("Shutting down scheduler...")
            scheduler.shutdown()
            logger.info("Scheduler shut down successfully")
    else:
        main()
