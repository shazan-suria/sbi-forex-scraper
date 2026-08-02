import requests
import pdfplumber
import pandas as pd
import json
import os
import re
from datetime import datetime
import urllib3

# Silence SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SBI_PDF_URL = "https://sbi.co.in/documents/16012/1400784/FOREX_CARD_RATES.pdf"
PDF_FILENAME = "daily_sbi_rates.pdf"
JSON_FILENAME = "sbi_tt_rates.json"

def download_pdf():
    print("Downloading today's SBI Forex PDF...")
    response = requests.get(SBI_PDF_URL, verify=False)
    with open(PDF_FILENAME, 'wb') as f:
        f.write(response.content)
    print("Download complete.")

def extract_rate():
    print("Extracting data from PDF...")
    
    with pdfplumber.open(PDF_FILENAME) as pdf:
        first_page = pdf.pages[0]
        
        # 1. Extract raw text first to grab the official publication date
        page_text = first_page.extract_text()
        
        # Extract date string like "01-08-2026"
        date_match = re.search(r'(\d{2}-\d{2}-\d{4})', page_text)
        if date_match:
            raw_date = date_match.group(1) # e.g. "01-08-2026"
            # Format to MM/DD/YYYY for our extension dictionary
            dt_obj = datetime.strptime(raw_date, "%d-%m-%Y")
            formatted_date = dt_obj.strftime("%m/%d/%Y")
        else:
            formatted_date = datetime.now().strftime("%m/%d/%Y")

        # 2. Extract the table
        table = first_page.extract_table()
        
    if not table:
        raise ValueError("No table structure found in PDF.")

    df = pd.DataFrame(table)

    # 3. Search every cell to find the row containing USD
    usd_mask = df.apply(lambda row: row.astype(str).str.contains("UNITED STATES DOLLAR|USD", case=False).any(), axis=1)
    usd_rows = df[usd_mask]

    if usd_rows.empty:
        raise ValueError("Could not find USD in the PDF table.")

    usd_row = usd_rows.iloc[0].tolist()

    # 4. Filter numeric values from the row (excluding currency codes like 93.85, 95.03, etc.)
    # In SBI's layout: [CN BUY, CURRENCY, TT BUY, TT SELL, BILL BUY, BILL SELL, ...]
    # For USD: ['93.85', 'UNITED STATES DOLLAR \n USD/INR', '95.03', '95.88', ...]
    numeric_values = []
    for cell in usd_row:
        if cell:
            cleaned = str(cell).replace('\n', ' ').strip()
            # Find numbers with decimals (e.g. 95.03)
            matches = re.findall(r'\d+\.\d+', cleaned)
            numeric_values.extend([float(m) for m in matches])

    # The second decimal number in the USD row corresponds to TT BUY (95.03)
    if len(numeric_values) >= 2:
        tt_buying_rate = numeric_values[1] # Index 1 is TT BUY (Index 0 is CN BUY)
    else:
        raise ValueError("Could not locate TT BUY numeric value in USD row.")

    print(f"Detected Date: {formatted_date}")
    print(f"Extracted USD TT Buying Rate: ₹{tt_buying_rate}")

    return formatted_date, tt_buying_rate

def update_json(date_str, rate):
    if os.path.exists(JSON_FILENAME):
        with open(JSON_FILENAME, 'r') as f:
            rates_db = json.load(f)
    else:
        rates_db = {}

    rates_db[date_str] = rate
    
    with open(JSON_FILENAME, 'w') as f:
        json.dump(rates_db, f, indent=4)
        
    print(f"Successfully saved to {JSON_FILENAME}: {date_str} -> ₹{rate}")

def main():
    try:
        download_pdf()
        date_str, usd_rate = extract_rate()
        update_json(date_str, usd_rate)
        
        # Add this line to delete the PDF after a successful run
        os.remove(PDF_FILENAME) 
        print(f"Cleaned up {PDF_FILENAME}")
        
    except Exception as e:
        print(f"Error in pipeline: {e}")

if __name__ == "__main__":
    main()