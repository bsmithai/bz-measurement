"""
Real-time Solar Wind Bz Plotter
-------------------------------

This script fetches real-time solar wind magnetic field data from NOAA's 
Space Weather Prediction Center (SWPC) and plots the Bz component 
(the north-south direction) over time.

A negative Bz is a key indicator for geomagnetic storm potential.

Required libraries:
- requests: To fetch the data from the API.
- matplotlib: To create the real-time plot.

Install them using:
pip install requests matplotlib
"""
import matplotlib
matplotlib.use('TkAgg') # <-- ADDED: Force an interactive backend like Tkinter

import requests
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.dates import DateFormatter
from datetime import datetime, timedelta
import time
import sys

# --- Configuration ---
URL = "https://services.swpc.noaa.gov/products/solar-wind/mag-7-day.json"
POLL_INTERVAL_SECONDS = 60  # Poll every 60 seconds (1 minute)
HOURS_TO_DISPLAY = 6       # Show the last 6 hours of data
BZ_COLUMN_INDEX = 3         # Column index for 'bz_gsm' in the JSON array
TIME_COLUMN_INDEX = 0       # Column index for 'time_tag'

# --- Plot Setup ---
fig, ax = plt.subplots(figsize=(14, 7))

def fetch_and_parse_data():
    """
    Fetches data from the NOAA endpoint and parses it.
    
    Returns:
        tuple: A tuple containing two lists:
               - timestamps (list of datetime objects)
               - bz_values (list of floats)
    """
    try:
        response = requests.get(URL, timeout=10)
        # Raise an exception for bad status codes (like 404 or 500)
        response.raise_for_status()  
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data at {datetime.utcnow()} UTC: {e}")
        return [], []
    except requests.exceptions.JSONDecodeError:
        print(f"Error decoding JSON at {datetime.utcnow()} UTC. Data may be incomplete.")
        return [], []

    timestamps = []
    bz_values = []

    if not data or len(data) < 2:
        print("No data or invalid data format.")
        return [], []

    # Skip the header row (data[0])
    for row in data[1:]:
        try:
            # Parse time string: "2025-11-06 00:23:00.000"
            time_str = row[TIME_COLUMN_INDEX]
            dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S.%f")
            
            # Parse Bz value
            bz_str = row[BZ_COLUMN_INDEX]
            
            # Check for null/None values which can appear in the feed
            if bz_str is not None:
                bz_val = float(bz_str)
                timestamps.append(dt)
                bz_values.append(bz_val)
                
        except (ValueError, TypeError, IndexError) as e:
            # Skip rows with parsing errors (e.g., null, empty, or malformed data)
            # print(f"Skipping row with bad data: {row} - Error: {e}")
            pass
            
    return timestamps, bz_values

def animate(i):
    """
    This function is called periodically by FuncAnimation.
    It fetches, filters, and re-draws the plot.
    """
    all_times, all_bz = fetch_and_parse_data()
    
    if not all_times:
        # If fetching failed, just wait for the next interval
        return

    # Filter data to only include the last HOURS_TO_DISPLAY
    cutoff_time = datetime.utcnow() - timedelta(hours=HOURS_TO_DISPLAY)
    
    # Use list comprehensions for efficient filtering
    times_to_plot = [t for t in all_times if t >= cutoff_time]
    bz_to_plot = [bz for t, bz in zip(all_times, all_bz) if t >= cutoff_time]

    if not times_to_plot:
        print(f"No data in the last {HOURS_TO_DISPLAY} hours.")
        return

    # --- Plotting ---
    ax.clear()
    
    # Plot the main Bz line
    ax.plot(times_to_plot, bz_to_plot, label='Bz (GSM)', color='black', linewidth=1.5)

    # Add a critical horizontal line at 0 nT
    ax.axhline(0, color='black', linestyle='-', linewidth=1.0)

    # --- Shading (for clear visual indication) ---
    
    # Create an array of zeros for fill_between
    zeros = [0] * len(bz_to_plot)
    
    # Shade the area above 0 blue (Northward / Safe)
    ax.fill_between(times_to_plot, bz_to_plot, zeros, 
                    where=(bz_to_plot > zeros), 
                    facecolor='#87ceeb',  # Sky Blue
                    alpha=0.5, interpolate=True)
                    
    # Shade the area below 0 red (Southward / DANGER)
    ax.fill_between(times_to_plot, bz_to_plot, zeros, 
                    where=(bz_to_plot < zeros), 
                    facecolor='#f08080',  # Light Coral (Red)
                    alpha=0.7, interpolate=True, label='Southward Bz (Storm Potential)')

    # --- Formatting ---
    ax.set_title(f'Real-time Solar Wind Bz (Last {HOURS_TO_DISPLAY} Hours)\nUpdated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC')
    ax.set_ylabel('IMF Bz (nT)')
    ax.set_xlabel('Time (UTC)')
    
    # Format the x-axis to show dates and times nicely
    ax.xaxis.set_major_formatter(DateFormatter('%H:%M'))
    fig.autofmt_xdate() # Auto-rotate date labels
    
    ax.grid(True, linestyle=':', alpha=0.7)
    
    # Set Y-axis limits to be symmetrical and provide some padding
    if bz_to_plot:
        # Find the largest absolute value for symmetrical Y-axis, default to at least 10
        max_abs_val = max(abs(min(bz_to_plot)), abs(max(bz_to_plot)), 10) 
        ax.set_ylim(-max_abs_val - 5, max_abs_val + 5)
    
    # Add a legend
    # Use a dictionary to avoid duplicate labels if one condition isn't met
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc='upper left')

def main():
    """Main function to run the animation."""
    
    # Add a note for required libraries
    print("-------------------------------------------------------------------")
    print("This script requires the 'requests' and 'matplotlib' libraries.")
    print("If not installed, run: pip install requests matplotlib")
    print("-------------------------------------------------------------------")
    time.sleep(1)

    print(f"Starting real-time Bz plotter...")
    print(f"Polling {URL} every {POLL_INTERVAL_SECONDS} seconds.")
    print("A plot window will open. Press Ctrl+C in this terminal to stop.")

    try:
        # Create the animation
        # The 'animate' function will be called immediately, and then every 'interval' milliseconds
        ani = animation.FuncAnimation(fig, animate, 
                                      interval=POLL_INTERVAL_SECONDS * 1000, 
                                      save_count=0) # save_count=0 prevents caching
                                      
        plt.show()
        
    except KeyboardInterrupt:
        print("Stopping plotter.")
        sys.exit(0)

if __name__ == "__main__":
    main()
