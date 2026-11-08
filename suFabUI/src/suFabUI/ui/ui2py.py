import subprocess

def run_command_and_print_output(command):
    """
    Runs a command using subprocess and prints its output and errors.
    
    Args:
    command (list): The command to run, represented as a list of strings.
    """
    try:
        print(f"Run {command}")
        # Running the command
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Capturing the output and error
        output, error = process.communicate()

        # Printing the output and error
        print("Output:")
        print(output)
        if error:
            print("Error:")
            print(error)

    except Exception as e:
        print("An error occurred while running the command:", str(e))
# run_command_and_print_output("pyuic5 main_window.ui -o ../src/ui_mainwindow.py")
# run_command_and_print_output("pyuic5 printer_setting.ui -o ../src/ui_printer_setting.py")
# run_command_and_print_output("pyuic5 about.ui -o ../src/ui_about.py")
# run_command_and_print_output("pyrcc5 resource.qrc -o ../src/resource_rc.py")
cmd_str = ("pyuic5 main_window.ui -o ../src/ui_mainwindow.py",
           "pyuic5 printer_setting.ui -o ../src/ui_printer_setting.py",
           "pyuic5 about.ui -o ../src/ui_about.py",
           "pyrcc5 resource.qrc -o ../resource_rc.py"
           )
# run_command_and_print_output("pyuic5 main_window.ui -o ../src/ui_mainwindow.py")
# run_command_and_print_output("pyuic5 printer_setting.ui -o ../src/ui_printer_setting.py")
# run_command_and_print_output("pyuic5 about.ui -o ../src/ui_about.py")
# run_command_and_print_output("pyrcc5 resource.qrc -o ../resource_rc.py")
for c in cmd_str:
    run_command_and_print_output(c)