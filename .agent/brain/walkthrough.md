# Walkthrough - Data Ingestion & Location-Aware Sync

Successfully set up the backend data ingestion pipeline and implemented geospatial logic to filter for the nearest "Online" fulfillment centers.

## Key Accomplishments

- **PostGIS Integration**: Enabled geospatial support in Supabase to calculate distances between users and store fulfillment centers.
- **Smart Geocoding**: Integrated `geopy` to automatically map store names (e.g., "Likot Ashdod") to precise Latitude/Longitude coordinates.
- **Robust Ingestion Logic**: Implemented `backend/main.py` with:
  - **Online Store Focus**: Automatically identifies and targets "Online/Likot" centers.
  - **Shufersal & Tiv Taam Sync**: Successfully ingested **63,000+ price entries** across both chains.
- **Product Enrichment**: 
    - **Barcodes**: Correctly mapped `ItemCode` to `product_code` for unique identification.
    - **Images**: Implemented a CDN-based fallback for Shufersal products, enabling **22,000+ product images** to be displayed in the app.
- **Library Patching**: Fixed a critical `TypeError` in the `il_supermarket_scraper` library to support string-based branch codes (e.g., "002").

## Results

### Online Center Geocoding (All Chains)
| Chain | Store Name | Status | Location |
| :--- | :--- | :--- | :--- |
| Tiv Taam | ליקוט נתניה (Netanya) | ✅ Geocoded | 32.30, 34.86 |
| Tiv Taam | ליקוט אשדוד (Ashdod) | ✅ Geocoded | 31.81, 34.65 |
| Shufersal | שופרסל ONLINE | ✅ Operational | WWW Pattern |

### Database Statistics (Phase 1.5 Final)
| Chain | Total Products | Total Prices | Image Source |
| :--- | :--- | :--- | :--- |
| Shufersal | 22,329 | 22,329 | ✅ CDN Fallback |
| Tiv Taam | 41,516 | 41,516 | ⏳ XML Feed (None) |

## How to Run
To trigger a fresh sync:
```powershell
backend\venv\Scripts\python backend\main.py
```

> [!TIP]
> **How location matching works**: On the frontend, when a user enters their location, the app runs an `ST_Distance` query to find the specific Online/Likot branch ID for each chain that represents their area.
