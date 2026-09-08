import tkinter as tk
from tkinter import ttk
import subprocess

def start_download():
    url = url_entry.get().strip()
    selected_quality = quality_var.get()
    
    if url:
        download_dir = r"C:\Users\zdenka.viktorova\Videos"
        
        # Build the command. If a specific quality is chosen, pass the -q flag
        q_flag = ""
        if selected_quality != "Highest Available":
            resolution = selected_quality.replace("p", "")
            q_flag = f"-q {resolution}"
            
        command = f'start cmd /k "ct-dlp {q_flag} ""{url}"""'
        
        subprocess.Popen(command, shell=True, cwd=download_dir)
        url_entry.delete(0, tk.END) # Clears the box for the next link

# Build the main window
root = tk.Tk()
root.title("ČT Downloader")
root.geometry("550x170")
root.resizable(False, False)

# Add the text and input box
tk.Label(root, text="Paste Česká televize URL:", font=("Segoe UI", 11)).pack(pady=(10, 5))
url_entry = tk.Entry(root, width=60, font=("Segoe UI", 10))
url_entry.pack(pady=5)

# Add the Quality Dropdown menu
quality_var = tk.StringVar(value="Highest Available")
quality_dropdown = ttk.Combobox(root, textvariable=quality_var, state="readonly", font=("Segoe UI", 9), width=18)
quality_dropdown['values'] = ("Highest Available", "1080p", "720p", "540p", "360p")
quality_dropdown.pack(pady=(0, 10))

# Add the download button
tk.Button(root, text="Download Video", command=start_download, font=("Segoe UI", 10, "bold"), bg="#E2001A", fg="white", width=20).pack(pady=5)

root.mainloop()