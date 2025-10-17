#!/usr/bin/env python3
"""
Recording Manager - Utility to manage browser activity recordings

Usage:
    python manage_recordings.py clear              # Clear current recording
    python manage_recordings.py backup <name>      # Backup current recording
    python manage_recordings.py restore <name>     # Restore a backup
    python manage_recordings.py list               # List all backups
    python manage_recordings.py info               # Show current recording info
"""

import json
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path


class RecordingManager:
    """Manage browser activity recordings"""
    
    RECORDING_FILE = "activity_log.json"
    BACKUP_DIR = "recording_backups"
    SCREENSHOTS_DIR = "screenshots"
    SCREENSHOTS_BACKUP_DIR = "screenshot_backups"
    
    def __init__(self):
        # Create backup directories if they don't exist
        os.makedirs(self.BACKUP_DIR, exist_ok=True)
        os.makedirs(self.SCREENSHOTS_BACKUP_DIR, exist_ok=True)
    
    def clear_recording(self):
        """Clear the current recording"""
        if not os.path.exists(self.RECORDING_FILE):
            print("✓ No recording to clear (activity_log.json doesn't exist)")
            return
        
        # Check if recording has content
        try:
            with open(self.RECORDING_FILE, 'r') as f:
                activities = json.load(f)
            
            if not activities:
                print("✓ Recording already empty")
                return
            
            count = len(activities)
            print(f"⚠️  Current recording has {count} activities")
            
            # Ask for confirmation
            response = input("Are you sure you want to clear it? (yes/no): ").strip().lower()
            
            if response not in ['yes', 'y']:
                print("❌ Clear cancelled")
                return
            
            # Create automatic backup before clearing
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"auto_backup_{timestamp}"
            print(f"📦 Creating automatic backup: {backup_name}")
            self.backup_recording(backup_name, auto=True)
            
        except Exception as e:
            print(f"⚠️  Warning: Could not read current recording: {e}")
        
        # Clear the recording
        with open(self.RECORDING_FILE, 'w') as f:
            json.dump([], f, indent=2)
        
        print("✅ Recording cleared! Ready for new recording.")
        print(f"   Backup saved to: {self.BACKUP_DIR}/{backup_name}.json")
        print("\nTo start new recording:")
        print("   python main.py")
    
    def backup_recording(self, name, auto=False):
        """Backup the current recording with a given name"""
        if not os.path.exists(self.RECORDING_FILE):
            print("❌ No recording to backup (activity_log.json doesn't exist)")
            return
        
        # Load current recording
        with open(self.RECORDING_FILE, 'r') as f:
            activities = json.load(f)
        
        if not activities and not auto:
            print("⚠️  Warning: Recording is empty")
            response = input("Backup anyway? (yes/no): ").strip().lower()
            if response not in ['yes', 'y']:
                print("❌ Backup cancelled")
                return
        
        # Create backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{self.BACKUP_DIR}/{name}_{timestamp}.json"
        
        # Save backup
        shutil.copy2(self.RECORDING_FILE, backup_file)
        
        # Backup screenshots if they exist
        if os.path.exists(self.SCREENSHOTS_DIR):
            screenshot_backup = f"{self.SCREENSHOTS_BACKUP_DIR}/{name}_{timestamp}"
            try:
                shutil.copytree(self.SCREENSHOTS_DIR, screenshot_backup)
                print(f"✅ Recording backed up: {backup_file}")
                print(f"✅ Screenshots backed up: {screenshot_backup}")
            except:
                print(f"✅ Recording backed up: {backup_file}")
                print(f"⚠️  Could not backup screenshots")
        else:
            print(f"✅ Recording backed up: {backup_file}")
        
        print(f"   Activities: {len(activities)}")
    
    def restore_recording(self, name):
        """Restore a recording from backup"""
        # Find matching backup
        backups = []
        for filename in os.listdir(self.BACKUP_DIR):
            if filename.startswith(name) and filename.endswith('.json'):
                backups.append(filename)
        
        if not backups:
            print(f"❌ No backup found matching '{name}'")
            print("\nAvailable backups:")
            self.list_backups()
            return
        
        if len(backups) > 1:
            print(f"⚠️  Multiple backups found matching '{name}':")
            for i, backup in enumerate(backups, 1):
                backup_path = f"{self.BACKUP_DIR}/{backup}"
                size = os.path.getsize(backup_path)
                mtime = datetime.fromtimestamp(os.path.getmtime(backup_path))
                print(f"   {i}. {backup} ({size} bytes, {mtime.strftime('%Y-%m-%d %H:%M:%S')})")
            
            choice = input("\nEnter number to restore (or 'cancel'): ").strip()
            if choice.lower() == 'cancel':
                print("❌ Restore cancelled")
                return
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(backups):
                    backup_file = backups[idx]
                else:
                    print("❌ Invalid choice")
                    return
            except:
                print("❌ Invalid choice")
                return
        else:
            backup_file = backups[0]
        
        backup_path = f"{self.BACKUP_DIR}/{backup_file}"
        
        # Backup current recording if it exists
        if os.path.exists(self.RECORDING_FILE):
            print("📦 Backing up current recording before restore...")
            self.backup_recording("before_restore", auto=True)
        
        # Restore the backup
        shutil.copy2(backup_path, self.RECORDING_FILE)
        
        # Try to restore screenshots
        screenshot_backup = backup_file.replace('.json', '')
        screenshot_backup_path = f"{self.SCREENSHOTS_BACKUP_DIR}/{screenshot_backup}"
        
        if os.path.exists(screenshot_backup_path):
            if os.path.exists(self.SCREENSHOTS_DIR):
                shutil.rmtree(self.SCREENSHOTS_DIR)
            shutil.copytree(screenshot_backup_path, self.SCREENSHOTS_DIR)
            print(f"✅ Recording restored: {backup_file}")
            print(f"✅ Screenshots restored")
        else:
            print(f"✅ Recording restored: {backup_file}")
            print(f"⚠️  No screenshots found for this backup")
        
        # Show info
        with open(self.RECORDING_FILE, 'r') as f:
            activities = json.load(f)
        print(f"   Activities: {len(activities)}")
    
    def list_backups(self):
        """List all available backups"""
        backups = []
        for filename in os.listdir(self.BACKUP_DIR):
            if filename.endswith('.json'):
                backup_path = f"{self.BACKUP_DIR}/{filename}"
                size = os.path.getsize(backup_path)
                mtime = datetime.fromtimestamp(os.path.getmtime(backup_path))
                
                # Load to get activity count
                try:
                    with open(backup_path, 'r') as f:
                        activities = json.load(f)
                    count = len(activities)
                except:
                    count = "?"
                
                backups.append({
                    'name': filename,
                    'size': size,
                    'date': mtime,
                    'count': count
                })
        
        if not backups:
            print("📁 No backups found")
            return
        
        print(f"📁 Available backups ({len(backups)}):\n")
        backups.sort(key=lambda x: x['date'], reverse=True)
        
        for backup in backups:
            date_str = backup['date'].strftime('%Y-%m-%d %H:%M:%S')
            size_kb = backup['size'] / 1024
            print(f"   • {backup['name']}")
            print(f"     Date: {date_str}")
            print(f"     Size: {size_kb:.1f} KB")
            print(f"     Activities: {backup['count']}")
            print()
    
    def show_info(self):
        """Show information about current recording"""
        if not os.path.exists(self.RECORDING_FILE):
            print("📄 No current recording (activity_log.json doesn't exist)")
            print("\nTo start recording:")
            print("   python main.py")
            return
        
        try:
            with open(self.RECORDING_FILE, 'r') as f:
                activities = json.load(f)
        except Exception as e:
            print(f"❌ Error reading recording: {e}")
            return
        
        print(f"📄 Current Recording Info:\n")
        print(f"   File: {self.RECORDING_FILE}")
        
        if not activities:
            print(f"   Status: Empty (ready for new recording)")
            return
        
        size = os.path.getsize(self.RECORDING_FILE)
        mtime = datetime.fromtimestamp(os.path.getmtime(self.RECORDING_FILE))
        
        print(f"   Activities: {len(activities)}")
        print(f"   Size: {size / 1024:.1f} KB")
        print(f"   Last modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Count activity types
        action_counts = {}
        for activity in activities:
            action = activity.get('action', 'unknown')
            action_counts[action] = action_counts.get(action, 0) + 1
        
        print(f"\n   Activity breakdown:")
        for action, count in sorted(action_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"      {action}: {count}")
        
        # Check for Phase 1 locators
        has_locators = any('locators' in activity for activity in activities)
        if has_locators:
            print(f"\n   ✅ Enhanced locators captured (Phase 1)")
        else:
            print(f"\n   ⚠️  Legacy recording (no enhanced locators)")
        
        # Check for VLM descriptions
        has_vlm = any('vlm_description' in activity for activity in activities)
        if has_vlm:
            print(f"   ✅ VLM descriptions included")
        
        # Screenshot info
        if os.path.exists(self.SCREENSHOTS_DIR):
            screenshot_count = len([f for f in os.listdir(self.SCREENSHOTS_DIR) if f.endswith('.png')])
            print(f"\n   Screenshots: {screenshot_count} files")
        
        print(f"\nTo replay this recording:")
        print(f"   python replay_browser_activities.py")


def print_usage():
    """Print usage information"""
    print(__doc__)
    print("\nExamples:")
    print("   python manage_recordings.py clear")
    print("   python manage_recordings.py backup my_test")
    print("   python manage_recordings.py restore my_test")
    print("   python manage_recordings.py list")
    print("   python manage_recordings.py info")


def main():
    if len(sys.argv) < 2:
        print_usage()
        return
    
    manager = RecordingManager()
    command = sys.argv[1].lower()
    
    if command == 'clear':
        manager.clear_recording()
    
    elif command == 'backup':
        if len(sys.argv) < 3:
            print("❌ Please provide a backup name")
            print("   Usage: python manage_recordings.py backup <name>")
            return
        name = sys.argv[2]
        manager.backup_recording(name)
    
    elif command == 'restore':
        if len(sys.argv) < 3:
            print("❌ Please provide a backup name")
            print("   Usage: python manage_recordings.py restore <name>")
            return
        name = sys.argv[2]
        manager.restore_recording(name)
    
    elif command == 'list':
        manager.list_backups()
    
    elif command == 'info':
        manager.show_info()
    
    else:
        print(f"❌ Unknown command: {command}")
        print_usage()


if __name__ == '__main__':
    main()
