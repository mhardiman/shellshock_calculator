#####################################################################################################
# shot_calculator.py                                                                                #
# __________________                                                                                #
#                                                                                                   #
# Find the angle to hit the target for a (X,Y) begin and end location for ShellShock Live.          #
#                                                                                                   #
#####################################################################################################

import win32gui
import win32api
import time
import math
import tkinter as tk
import numpy as np
import pyHook
import pythoncom

alpha = 4.015e-4# Where g = alpha * V^2, where V is the maximum speed.
beta = 5.081e-7# Where acceleration due to wind is beta * wind * V^2.
res = np.array([1768, 992])# Actual resolution of the game display.
nom_res = np.array([1920, 1080])# Resolution that alpha & beta correspond to.
scale = nom_res/res
ERROR_THRESH = 5 # Maximum pixels of error for windy shots.
NOT_ENOUGH_POWER = 360 # Return value for angle calculation if not enough power.

def sind(x):
    return math.sin(x*math.pi/180)

def calc_angles(x, y, p):
    root_term = math.pow(p,4) - math.pow(alpha*x,2) + 2*alpha*y*math.pow(p,2)
    if root_term < 0:
        return (NOT_ENOUGH_POWER, NOT_ENOUGH_POWER)
    denom_term = alpha * x
    angle_p = math.atan((math.pow(p,2) + math.sqrt(root_term)) / denom_term)*180/math.pi
    angle_m = math.atan((math.pow(p,2) - math.sqrt(root_term)) / denom_term)*180/math.pi
    return (angle_p, angle_m)

def calc_wind_offset(y, p, angle, wind):
    t = (p * sind(angle) + math.sqrt(math.pow(p,2) * math.pow(sind(angle),2) + 2*alpha*y))/alpha
    offset = beta * wind * math.pow(t,2)/2
    return offset

class Application(tk.Frame):
    count = 0
    x = np.zeros(2)
    y = np.zeros(2)
    hm = pyHook.HookManager()
    scale_pos = 100.0

    def do_calc(self, pos):
        self.scale_pos = pos
        wind = 0
        if self.has_wind.get():
            wind = int(self.wind_txt.get("1.0", "end-1c"))# Get wind as an integer and delete ending newline.
            print("wind = %d" % wind)

        if self.x[0] == self.x[1]:# Handle program startup.
            return 0

        x_diff = self.x[1] - self.x[0]
        y_diff = self.y[1] - self.y[0]

        # Account for different resolutions.
        x_diff *= scale[0]
        y_diff *= scale[1]

        # Convert to fraction 0-1.
        p = pos/100.0

        angles = np.zeros(2) # Holds positive and then negative angle.
        # Get the two possible angles to hit the target without wind.
        angles = calc_angles(x_diff, y_diff, p)
        if angles[0] == NOT_ENOUGH_POWER:# Could improve this to take into account wind.
            self.txt.insert(tk.END, "   Not enough power.\n")
            self.txt.see(tk.END)
            return 0

        if wind != 0:
            # Find each of the two possible angles one-by-one.
            for i in range(0,1):
                # Using the no-wind target, find how far off we far.
                offset = calc_wind_offset(y_diff, p, math.fabs(angles[i]), wind) # Add support for both angles.
                error = offset
                print("x_diff*dir = %d" % x_diff)
                print("Initial error = %f" % error)
                iters = 0
                target = x_diff
                # Run closed-loop guess-and-check iteratively until we converge to a small enough error.
                while math.fabs(error) > ERROR_THRESH:
                    # Choose new x position to target based on previous error.
                    target = target - error
                    print("target = %f" % target)
                    # Get new angles to hit this target.
                    angles = calc_angles(target, y_diff, p)
                    if angles[i] == NOT_ENOUGH_POWER:
                        self.txt.insert(tk.END, "   Not enough power.\n")
                        self.txt.see(tk.END)
                        return 0
                    # Find offset for the new target.
                    offset = calc_wind_offset(y_diff, p, math.fabs(angles[i]), wind)
                    hit_location = target + offset # Actual location where the shot landed.
                    error = hit_location - x_diff
                    print("error = %f" % error)
                    iters += 1
                    if iters > 10:
                        print("Exceeded iteration limit.")
                        self.txt.insert(tk.END, "   Exceeded iteration limit.\n")
                        self.txt.see(tk.END)
                        return 0

        out_str = "%5d%8.2f%8.2f\n" % (int(pos), angles[0], angles[1])
        self.txt.insert(tk.END, out_str)
        self.txt.see(tk.END)

    def scale_change(self, pos):
        self.do_calc(float(pos))
        return 0

    def on_rmb_click(self, event):
        self.x[self.count] = event.Position[0]
        self.y[self.count] = event.Position[1]
        self.count += 1
        if self.count == 2:
            self.hm.UnhookMouse()
            self.count = 0
            self.txt.insert(tk.END, "\n\nX = %d   Y = %d\n\n" % (self.x[1] - self.x[0], self.y[1] - self.y[0]))
            self.txt.see(tk.END)
            if self.x[1] == self.x[0]:
                self.txt.insert(tk.END, "Same x-coordinates.")
                self.txt.see(tk.END)
            else:
                self.do_calc(self.scale_pos)
        return 0

    def get_coords(self):
        self.hm.HookMouse()
        return

    def quit(self):
        self.root.destroy()

    def __init__(self, master=None):
        self.root = tk.Tk()
        tk.Frame.__init__(self, master)
        self.grid()
        self.createWidgets()
        
        self.hm.SubscribeMouseRightUp(self.on_rmb_click)#SubscribeMouseAllButtons()
        #pythoncom.PumpMessages() # Unnecessary since we have a GUI already doing this.

    def createWidgets(self):
        self.quit_button = tk.Button(self, text="Quit", command=self.quit)
        self.quit_button.grid()
        self.get_coords_btn = tk.Button(self, text="Select coordinates", width = 20, command=self.get_coords)
        self.get_coords_btn.grid(row=0, column=1)
        self.has_wind = tk.IntVar()
        self.wind_chkbtn = tk.Checkbutton(self, text="Wind", variable=self.has_wind)
        self.wind_chkbtn.grid(row=1, column=0)
        self.wind_txt = tk.Text(self, borderwidth=3, width = 5, height = 1)
        self.wind_txt.grid(row=2, column=0)
        self.power_scale = tk.Scale(self, from_=100, to=0, length=200, command=self.scale_change)
        self.power_scale.set(100)
        self.power_scale.grid(row=3, column=0)
        self.title_lbl = tk.Label(self, width=24, text="      P               ∠1                 ∠2           ")
        self.title_lbl.grid(row=2, column=1)
        self.txt = tk.Text(self, borderwidth=3, width=24 )
        self.txt.grid(row=3, column=1)

app = Application()
app.master.title('Shot Calculator')
app.mainloop()
