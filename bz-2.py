import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from matplotlib.dates import DateFormatter
from datetime import datetime, timedelta
import sys
import requests

plt.style.use('dark_background')

# --- Configuration ---
MAG_URL = "https://services.swpc.noaa.gov/products/solar-wind/mag-7-day.json"
PLASMA_URL = "https://services.swpc.noaa.gov/products/solar-wind/plasma-7-day.json"
HOURS_TO_DISPLAY = 6

# Distance from L1 to Earth in kilometers
L1_TO_EARTH_KM = 1500000

# --- Plot Setup ---
fig, ax = plt.subplots(figsize=(14, 7))
plt.subplots_adjust(bottom=0.15)

button_ax = plt.axes([0.45, 0.02, 0.1, 0.05])
button = Button(button_ax, 'Refresh', color='lightblue', hovercolor='skyblue')

def fetch_mag_data():
    """Fetch magnetic field data (includes Bz)"""
    try:
        response = requests.get(MAG_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        mag_dict = {}
        if data and len(data) >= 2:
            for row in data[1:]:  # Skip header
                try:
                    time_str = row[0]
                    dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S.%f")
                    bz = row[3]  # bz_gsm column
                    
                    if bz is not None:
                        mag_dict[dt] = float(bz)
                except (ValueError, TypeError, IndexError):
                    pass
        
        return mag_dict
    except Exception as e:
        print(f"Error fetching magnetic data: {e}")
        return {}

def fetch_plasma_data():
    """Fetch plasma data (includes speed)"""
    try:
        response = requests.get(PLASMA_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        plasma_dict = {}
        if data and len(data) >= 2:
            for row in data[1:]:  # Skip header
                try:
                    time_str = row[0]
                    dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S.%f")
                    speed = row[2]  # CORRECTED: speed is column 2
                    
                    if speed is not None:
                        plasma_dict[dt] = float(speed)
                except (ValueError, TypeError, IndexError):
                    pass
        
        return plasma_dict
    except Exception as e:
        print(f"Error fetching plasma data: {e}")
        return {}

def merge_data(mag_dict, plasma_dict):
    """
    Merge magnetic and plasma data by timestamp.
    Only includes times where we have both Bz and speed.
    """
    timestamps = []
    bz_values = []
    speed_values = []
    
    # Find common timestamps
    common_times = sorted(set(mag_dict.keys()) & set(plasma_dict.keys()))
    
    for dt in common_times:
        timestamps.append(dt)
        bz_values.append(mag_dict[dt])
        speed_values.append(plasma_dict[dt])
    
    return timestamps, bz_values, speed_values

def calculate_arrival_time(measurement_time, speed_km_s):
    """Calculate when solar wind measured at L1 will arrive at Earth."""
    if speed_km_s <= 0:
        return None
    
    transit_time_seconds = L1_TO_EARTH_KM / speed_km_s
    arrival_time = measurement_time + timedelta(seconds=transit_time_seconds)
    return arrival_time

def update_plot():
    """Fetches, filters, and re-draws the plot."""
    print("\nFetching data...")
    mag_dict = fetch_mag_data()
    plasma_dict = fetch_plasma_data()
    
    print(f"  Magnetic data points: {len(mag_dict)}")
    print(f"  Plasma data points: {len(plasma_dict)}")
    
    all_times, all_bz, all_speeds = merge_data(mag_dict, plasma_dict)
    
    print(f"  Merged data points: {len(all_times)}")
    
    if not all_times:
        print("No data available.")
        return
    
    if all_speeds:
        print(f"  Speed range: {min(all_speeds):.1f} - {max(all_speeds):.1f} km/s")

    # Filter data to only include the last HOURS_TO_DISPLAY
    cutoff_time = datetime.utcnow() - timedelta(hours=HOURS_TO_DISPLAY)
    
    times_to_plot = []
    bz_to_plot = []
    speeds_to_plot = []
    arrival_times = []
    
    for t, bz, speed in zip(all_times, all_bz, all_speeds):
        if t >= cutoff_time:
            times_to_plot.append(t)
            bz_to_plot.append(bz)
            speeds_to_plot.append(speed)
            arrival = calculate_arrival_time(t, speed)
            if arrival:
                arrival_times.append(arrival)
            else:
                arrival_times.append(None)

    if not times_to_plot:
        print(f"No data in the last {HOURS_TO_DISPLAY} hours.")
        return

    # Get latest measurements for info display
    latest_time = times_to_plot[-1]
    latest_bz = bz_to_plot[-1]
    latest_speed = speeds_to_plot[-1]
    latest_arrival = arrival_times[-1]

    # --- Plotting ---
    ax.clear()
    
    # Plot the main Bz line
    ax.plot(times_to_plot, bz_to_plot, label='Bz (GSM)', color='black', linewidth=1.5)

    # Add a critical horizontal line at 0 nT
    ax.axhline(0, color='black', linestyle='-', linewidth=1.0)

    # --- Shading ---
    zeros = [0] * len(bz_to_plot)
    
    ax.fill_between(times_to_plot, bz_to_plot, zeros, 
                    where=([bz > 0 for bz in bz_to_plot]), 
                    facecolor='#87ceeb',
                    alpha=0.5, interpolate=True)
                    
    ax.fill_between(times_to_plot, bz_to_plot, zeros, 
                    where=([bz < 0 for bz in bz_to_plot]), 
                    facecolor='#f08080',
                    alpha=0.7, interpolate=True, label='Southward Bz (Storm Potential)')

    # --- Formatting ---
    ax.set_title(f'Solar Wind Bz at L1 (Last {HOURS_TO_DISPLAY} Hours)\nMeasured: {latest_time.strftime("%Y-%m-%d %H:%M:%S")} UTC')
    ax.set_ylabel('Interplanetary Magnetic Field Bz (nanoTeslas)')
    ax.set_xlabel('Time (UTC)')
    
    ax.xaxis.set_major_formatter(DateFormatter('%H:%M'))
    fig.autofmt_xdate()
    
    ax.grid(True, linestyle=':', alpha=0.7)
    
    if bz_to_plot:
        max_abs_val = max(abs(min(bz_to_plot)), abs(max(bz_to_plot)), 10) 
        ax.set_ylim(-max_abs_val - 5, max_abs_val + 5)
    
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc='upper left')

    # --- Info Box with Arrival Time (BOTTOM LEFT) ---
    now = datetime.utcnow()
    
    if latest_arrival:
        transit_minutes = (latest_arrival - latest_time).total_seconds() / 60
        time_until_arrival = (latest_arrival - now).total_seconds() / 60
        
        if time_until_arrival > 0:
            arrival_status = f"Arrives at Earth: {latest_arrival.strftime('%H:%M:%S')} UTC\n({time_until_arrival:.1f} min from now)"
        else:
            arrival_status = f"Arrived at Earth: {latest_arrival.strftime('%H:%M:%S')} UTC\n({abs(time_until_arrival):.1f} min ago)"
    else:
        arrival_status = "Arrival time: Unknown"
        transit_minutes = 0
    
    info_text = (
        f"Latest Measurement (L1):\n"
        f"  Time: {latest_time.strftime('%H:%M:%S')} UTC\n"
        f"  Bz: {latest_bz:.2f} nT\n"
        f"  Speed: {latest_speed:.1f} km/s\n"
        f"  Transit Time: {transit_minutes:.1f} min\n"
        f"\n{arrival_status}"
    )
    
    ax.text(0.02, 0.02, info_text,
            horizontalalignment='left',
            verticalalignment='bottom',
            transform=ax.transAxes,
            fontsize=9,
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
            family='monospace')
    
    # Redraw the canvas
    fig.canvas.draw_idle()
    print(f"\nPlot updated at {datetime.utcnow().strftime('%H:%M:%S')} UTC")
    print(f"  Latest Bz: {latest_bz:.2f} nT | Speed: {latest_speed:.1f} km/s")
    if latest_arrival:
        print(f"  Expected Earth arrival: {latest_arrival.strftime('%H:%M:%S')} UTC")

def on_button_click(event):
    """Button click handler"""
    print("\n" + "="*60)
    print("Refreshing data...")
    print("="*60)
    update_plot()

button.on_clicked(on_button_click)

def main():
    """Main function"""
    print("-------------------------------------------------------------------")
    print("Solar Wind Bz Plotter with Earth Arrival Times")
    print("This script requires 'requests' and 'matplotlib' libraries.")
    print("-------------------------------------------------------------------")
    print("Showing measurements from DSCOVR at L1 Lagrange point")
    print("Earth arrival times calculated based on solar wind speed")
    print("Click 'Refresh' to update. Close window or Ctrl+C to exit.")
    print()
    
    update_plot()
    
    try:
        plt.show()
    except KeyboardInterrupt:
        print("\nStopping plotter.")
        sys.exit(0)

if __name__ == "__main__":
    main()
