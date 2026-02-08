import os
import glob
import logging
import datetime
import shutil
import xml.etree.ElementTree as ET
import gzip
from dotenv import load_dotenv
from supabase import create_client, Client
from il_supermarket_scarper.scrappers_factory import ScraperFactory
from il_supermarket_scarper.main import FileTypesFilters
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# Load environment variables
load_dotenv("credentials.env")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Supabase setup
SUBAPASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUBAPASE_URL or not SUPABASE_KEY:
    logging.error("Supabase URL or Key not found.")
    exit(1)

supabase: Client = create_client(SUBAPASE_URL, SUPABASE_KEY)

DATA_DIR = "backend/temp_data"

def clean_data_dir():
    if os.path.exists(DATA_DIR):
        shutil.rmtree(DATA_DIR)
    os.makedirs(DATA_DIR)

def get_chain_id(chain_code):
    res = supabase.table("chains").select("id").eq("code", chain_code).execute()
    if res.data:
        return res.data[0]['id']
    return None

def geocode_address(name, address, city):
    # Try multiple combinations
    geolocator = Nominatim(user_agent="supermarket_price_compare_v1")
    
    # Priority 1: Full Address + City (if city is not a numeric code)
    if address and city and not city.isdigit():
        full_address = f"{address}, {city}, Israel"
        try:
            location = geolocator.geocode(full_address, timeout=10)
            if location: return f"POINT({location.longitude} {location.latitude})"
        except: pass

    # Priority 2: Store Name (if it contains city)
    # Clean up "ליקוט" from name for better search
    clean_name = name.replace("ליקוט", "").strip()
    try:
        location = geolocator.geocode(f"{clean_name}, Israel", timeout=10)
        if location: return f"POINT({location.longitude} {location.latitude})"
    except: pass
    
    return None

def is_online_store(name, chain_code):
    if not name:
        return False
    name_l = name.lower()
    # Tiv Taam: Contains "ליקוט" (Likot)
    if "ליקוט" in name:
        return True
    # Shufersal: Contains "אונליין" (Online) or code 901
    if "אונליין" in name_l or "online" in name_l:
        return True
    # Generic online markers
    if "מרחבי" in name or "משלוחים" in name:
        return True
    return False

def sync_stores(chain_name, chain_code):
    logging.info(f"Syncing stores for {chain_name}...")
    chain_id = get_chain_id(chain_code)
    if not chain_id:
        logging.error(f"Chain {chain_code} not found in DB.")
        return

    # Download Store File
    scraper_cls = ScraperFactory.get(chain_name)
    scraper = scraper_cls(folder_name=DATA_DIR)
    scraper.scrape(limit=1, files_types=[FileTypesFilters.STORE_FILE.name])

    # The scraper creates a subfolder based on the chain name
    # We'll look for XML/GZ files specifically in that subfolder (or sub-subfolders)
    chain_folder = os.path.join(DATA_DIR, type(scraper).__name__)
    if not os.path.exists(chain_folder):
        # Fallback to broad search if scrapper_name doesn't match folder exactly
        chain_folder = DATA_DIR

    xml_files = glob.glob(f"{chain_folder}/**/*.xml", recursive=True)
    gz_files = glob.glob(f"{chain_folder}/**/*.gz", recursive=True)
    
    # Decompress GZ files
    for gz_path in gz_files:
        xml_path = gz_path.replace(".gz", "")
        if not os.path.exists(xml_path):
            logging.info(f"Decompressing {gz_path}...")
            with gzip.open(gz_path, 'rb') as f_in:
                with open(xml_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        xml_files.append(xml_path)

    if not xml_files:
        logging.warning(f"No store files found for {chain_name}")
        return

    for xml_path in list(set(xml_files)): # Use set to avoid double processing
        logging.info(f"Parsing stores from {xml_path}")
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        stores_to_upsert = []
        # XML structure varies slightly (Store vs STORE, StoreID vs STOREID)
        # Find all tags that look like a retail store entry
        stores_nodes = root.findall(".//Store") + root.findall(".//STORE")
        
        for store in stores_nodes:
            store_id = store.findtext("StoreID") or store.findtext("STOREID") or store.findtext("StoreId")
            name = store.findtext("StoreName") or store.findtext("STORENAME") or store.findtext("name")
            city = store.findtext("City") or store.findtext("CITY")
            address = store.findtext("Address") or store.findtext("ADDRESS")
            
            if store_id:
                store_data = {
                    "chain_id": chain_id,
                    "store_id_in_chain": store_id.strip(),
                    "name": name.strip() if name else None,
                    "city": city.strip() if city else None,
                    "address": address.strip() if address else None
                }
                
                # Check if it's an online store and geocode it
                if is_online_store(store_data["name"], chain_code):
                    logging.info(f"Online store found: {store_data['name']}. Geocoding...")
                    location_wkt = geocode_address(store_data["name"], store_data["address"], store_data["city"])
                    if location_wkt:
                        store_data["location"] = location_wkt
                        logging.info(f"Geocoded to {location_wkt}")
                    else:
                        logging.warning(f"Could not geocode online store: {store_data['name']}")
                
                stores_to_upsert.append(store_data)
        
        if stores_to_upsert:
            logging.info(f"Upserting {len(stores_to_upsert)} stores for {chain_name}")
            # Supabase upsert with conflict on (chain_id, store_id_in_chain)
            supabase.table("stores").upsert(stores_to_upsert, on_conflict="chain_id, store_id_in_chain").execute()

def sync_prices(chain_name, chain_code):
    logging.info(f"Syncing Online Prices for {chain_name}...")
    chain_id = get_chain_id(chain_code)
    if not chain_id:
        logging.error(f"Chain {chain_code} not found in DB.")
        return

    # 1. Identify Online Stores in DB
    db_stores = supabase.table("stores").select("id", "store_id_in_chain", "name").eq("chain_id", chain_id).execute()
    online_stores = [s for s in db_stores.data if is_online_store(s['name'], chain_code)]
    
    if not online_stores:
        logging.warning(f"No online stores found in DB for {chain_name}. Please sync stores first.")
        return

    logging.info(f"Found {len(online_stores)} online stores: {[s['name'] for s in online_stores]}")

    # Process Price Full files
    # Note: To avoid downloading thousands of files, we assume the stores we want 
    # are relatively few. The scraper usually pulls latest relevant files.
    scraper_cls = ScraperFactory.get(chain_name)
    scraper = scraper_cls(folder_name=DATA_DIR)
    
    for store in online_stores:
        store_id_in_chain = store['store_id_in_chain']
        db_store_id = store['id']
        logging.info(f"Processing Online store: {store['name']} ({store_id_in_chain})")
        
        # Request PriceFull for this specific store
        scraper.scrape(limit=1, files_types=[FileTypesFilters.PRICE_FULL_FILE.name], store_id=store_id_in_chain)

        # Look specifically in this chain's folder
        chain_folder = os.path.join(DATA_DIR, type(scraper).__name__)
        if not os.path.exists(chain_folder): chain_folder = DATA_DIR

        xml_files = glob.glob(f"{chain_folder}/**/*.xml", recursive=True)
        gz_files = glob.glob(f"{chain_folder}/**/*.gz", recursive=True)
        
        # Decompress GZ files
        for gz_path in gz_files:
            target_xml = gz_path.replace(".gz", "")
            if f"-{store_id_in_chain}-" in gz_path or "Price" in gz_path: # Basic heuristic
                 if not os.path.exists(target_xml):
                    logging.info(f"Decompressing {gz_path}...")
                    try:
                        with gzip.open(gz_path, 'rb') as f_in:
                            with open(target_xml, 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                    except Exception as e:
                        logging.error(f"Failed to decompress {gz_path}: {e}")
                 if target_xml not in xml_files: xml_files.append(target_xml)

        found_price_file = False
        for xml_path in xml_files:
            # Match store ID in filename or content
            filename = os.path.basename(xml_path)
            if "Price" not in filename: continue
            
            # Simple check if file belongs to this store
            if f"-{store_id_in_chain}-" not in filename:
                # Some chains don't put store ID in filename, peek inside if needed
                # But mostly they do or it's in the header
                pass
            
            found_price_file = True
            logging.info(f"Parsing prices from {xml_path}")
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # Verify StoreID in header
            xml_store_id = root.findtext("StoreID") or root.findtext("StoreId")
            if xml_store_id and xml_store_id.strip() != store_id_in_chain:
                continue

        items = root.findall(".//Item") + root.findall(".//ITEM")
        logging.info(f"Found {len(items)} items in file for store {store_id_in_chain}.")
        
        # First pass: collect all product info to upsert products
        all_products_dict = {}
        all_prices_data = [] # List of (code, price)
        
        for item in items:
            code_raw = item.findtext("ItemCode") or item.findtext("item_code") or item.findtext("barcode")
            if not code_raw: continue
            code = code_raw.strip()
            name = item.findtext("ItemName") or item.findtext("item_name")
            manufacturer = item.findtext("ManufacturerName") or item.findtext("manufacturer")
            unit = item.findtext("UnitOfMeasure") or item.findtext("unit_of_measure")
            price = item.findtext("ItemPrice") or item.findtext("item_price") or item.findtext("Price")
            image_url = item.findtext("ItemImage") or item.findtext("item_image") or item.findtext("image")
            
            if not image_url and chain_code == "SHUFERSAL":
                image_url = f"https://res.cloudinary.com/shufersal/image/upload/f_auto,q_auto/v1/shufersal_auto/p/{code}"

            all_products_dict[code] = {
                "chain_id": chain_id,
                "product_code": code,
                "name": name.strip() if name else "Unknown Product",
                "manufacturer_name": manufacturer.strip() if manufacturer else None,
                "unit_of_measure": unit.strip() if unit else None,
                "image_url": image_url.strip() if image_url else None
            }
            if price:
                all_prices_data.append((code, price))

        # Upsert products and collect IDs
        prod_list = list(all_products_dict.values())
        logging.info(f"Upserting {len(prod_list)} unique products and mapping IDs...")
        code_to_id = {}
        for i in range(0, len(prod_list), 1000):
            batch_prods = prod_list[i:i+1000]
            res = supabase.table("products").upsert(batch_prods, on_conflict="chain_id, product_code").execute()
            for p in res.data:
                code_to_id[p['product_code']] = p['id']

        # Prepare unique price entries
        final_prices_dict = {}
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for code, price in all_prices_data:
            if code in code_to_id:
                try:
                    price_val = float(price)
                    final_prices_dict[code] = {
                        "product_id": code_to_id[code],
                        "store_id": db_store_id,
                        "price": price_val,
                        "price_update_date": now_ts,
                        "is_promotion": False
                    }
                except ValueError:
                    continue
        
        # Upsert prices in batches
        price_list = list(final_prices_dict.values())
        logging.info(f"Upserting {len(price_list)} price entries...")
        upsert_batch_size = 500
        for i in range(0, len(price_list), upsert_batch_size):
            batch = price_list[i:i+upsert_batch_size]
            try:
                supabase.table("prices").upsert(batch, on_conflict="product_id, store_id").execute()
                if (i // upsert_batch_size) % 5 == 0:
                    logging.info(f"Uploaded {i + len(batch)} / {len(price_list)} prices...")
            except Exception as e:
                logging.error(f"Error upserting prices batch {i}: {e}")
                # Print first item to debug
                if batch:
                    logging.error(f"Sample item: {batch[0]}")
                raise e
            
            if (i // upsert_batch_size) % 5 == 0:
                logging.info(f"Processed {i + len(batch)} / {len(price_list)} price entries...")

    if not found_price_file:
        logging.warning(f"No price XML found for {chain_name} in {DATA_DIR}")

if __name__ == "__main__":
    clean_data_dir()
    # Tiv Taam
    sync_stores("TIV_TAAM", "TIV_TAAM")
    sync_prices("TIV_TAAM", "TIV_TAAM")
    
    # Shufersal
    # Note: Shufersal scraper might take longer due to pagination/Cookies
    sync_stores("SHUFERSAL", "SHUFERSAL")
    sync_prices("SHUFERSAL", "SHUFERSAL")
