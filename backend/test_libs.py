from il_supermarket_scarper.scrappers_factory import ScraperFactory
from il_supermarket_parsers.parser_factory import ParserFactory

print("--- Scrapers ---")
print("Supported Scrapers:", ScraperFactory.get_all_scapers_names())

print("\n--- Parsers ---")
# Let's see what ParserFactory has
import inspect
methods = inspect.getmembers(ParserFactory, predicate=inspect.ismethod)
print("ParserFactory Methods:", [m[0] for m in methods])
# If no methods, check static/class attributes
print("ParserFactory dir:", dir(ParserFactory))

# Try to get all parser names
try:
    print("All Parsers:", ParserFactory.all_parsers())
except Exception as e:
    print(f"Could not call all_parsers: {e}")
