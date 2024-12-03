import os

def rename_json_files_in_current_directory(old_prefix, new_prefix):
    """
    Renames all JSON files in the current directory by replacing the old prefix with a new one.
    Args:
        old_prefix (str): The prefix to be replaced in the filenames.
        new_prefix (str): The new prefix to replace the old one.
    """
    current_directory = os.getcwd()
    for filename in os.listdir(current_directory):
        if filename.endswith(".json") and filename.startswith(old_prefix):
            # Replace only the prefix
            new_filename = filename.replace(old_prefix, new_prefix, 1)
            # Rename the file
            os.rename(filename, new_filename)
            print(f"Renamed: {filename} -> {new_filename}")

# Example usage
if __name__ == "__main__":
    old_prefix = "test2"
    new_prefix = "AccordXRT2"
    rename_json_files_in_current_directory(old_prefix, new_prefix)
