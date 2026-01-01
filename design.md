# Overview
BricksWhere is a desktop GUI application that helps LEGO collectors organize their collections of LEGO parts. The application enables users to:
- quickly find the parts and colors they need to assemble a LEGO model
- quickly return loose parts and colors to their collection
LEGO parts are identified by manufacturer part numbers and these are displayed throughout the application.
Most parts are available in multiple colors. We follow the Rebrickable convention for colors: Rebrickable provides a CSV table that includes a color ID (suitable for a database key) and a human-readable color name. Users best understand color names, so the UI displays color names rather than internal numeric IDs.
The combination of a part and a color is called an "element". For example, a black 1x1 brick and a blue 1x1 brick are the same part but different elements.
We use the term "bin" for a physical container (bag, tray, drawer, box, etc.). Each bin has a unique user-assigned label which the app displays and uses when mapping elements to physical locations.
A LEGO set contains a fixed collection of elements (parts in particular colors). Users can "part out" a set — moving the elements from the set into their bins — and may add or update bins as needed.
# Main Features
The primary features are:
- Navigate the replica of Rebrickable tables in a user-friendly tree and search UI.
- Display images (for the selected part or set) using the HTTP cache and background fetching.
- Allow users to annotate replica data with persistent user data stored in application tables (for example `user_sets`).
- Produce printable reports that list bins and elements to retrieve.
- Track sets the user owns and compute aggregate part quantities across the collection.
- Allow the user to add or remove elements from their collection manually and persist those changes.
# Dependencies
The application is implemented in Python. The UI uses Qt via PySide6. The local database is SQLite. Additional runtime libraries in the repository include `requests-cache` (optional) for HTTP response caching. BricksWhere is distributed under the MIT license and dependencies should be license-compatible.
# Database
## Local Replica
The application uses a local SQLite database that contains three broad categories of tables:
1. A read-only replica of Rebrickable's CSV tables. These tables are only modified during an explicit synchronization run (or the initial sync when the database is first created).
2. Tables used by the HTTP cache (see HTTP Cache below).
3. User-provided persistent tables (e.g., `user_sets`, bin mappings, quantities, remarks).
We avoid scraping Rebrickable HTML pages; the app uses the published CSV download URLs already hard coded in the source code. Synchronization is performed only on user request (or initially on first run) to reduce load on Rebrickable.
We intentionally do not add user columns to the replica tables. Persistent user data is stored in separate application tables that reference replica IDs (for example `part_num` or `color_id`).
### Local Replica Schema
The repository defines the replica tables that map directly to Rebrickable CSV files (for example `parts`, `colors`, `sets`, `elements`, `themes`, `inventories`, `inventory_parts`, etc.). Schema details are implemented in `model/db.py` and created programmatically by `create_schema(conn)`.
Key application tables include `user_sets` (see below) and the replica tables used for lookups and read-only queries.
## HTTP Cache
Images and other HTTP resources are fetched on demand and cached locally. The application uses `requests-cache` (when available) with a SQLite backend so cached HTTP responses are persisted in the application's database file. This reduces repeated downloads and respects HTTP cache headers when possible. The code falls back to `requests` if `requests-cache` is not installed.
Note: the current implementation uses the application DB path as the cache backing store via `requests_cache.CachedSession(cache_name=db_path, backend='sqlite')`. This is an implementation detail; the important design point is that HTTP responses are cached persistently and reused across runs.
# Architecture
The project uses Model-View-ViewModel (MVVM). Business logic, I/O, and data storage live in `model/`. UI orchestration and testable presentation logic live in `viewmodel/`. UI widgets live in `view/` and should be thin; views interact with view-models through callbacks, signals, and small public APIs.
Tests are organized alongside the code under `model/tests/`, `viewmodel/tests/`, and `view/tests/`. The test suite uses `pytest` and may use `pytest-qt` for UI tests; note that Qt-based tests are inherently more complex and may be flaky in some environments.
# User Interface
Many UI widgets must be updated after a synchronization or when the user changes persistent data. The implementation uses view-models to keep views thin and testable; view-models notify views via callbacks or signals so UI components can update themselves.
The codebase exposes application-level hooks and testing helpers (for example `DirectoryViewModel.flush_search()` and a dialog-created signal on `MainWindow`) to facilitate deterministic unit tests of UI-related behavior.
## Synchronization Progress Dialog
While synchronizing with Rebrickable the application shows a progress dialog with a message list and progress bar. The dialog provides a Cancel button; requesting cancel causes the synchronization to stop and the database changes to be rolled back. When synchronization completes (successfully, failed, or cancelled) the dialog switches to an OK state and can be dismissed.
## Directory Window
The Directory panel (docked on the left by default) contains a tree with top-level "Parts" and "Sets" nodes and a search control. Expanding categories or themes causes the app to request items only for the expanded groups to keep SQL queries efficient. The search box supports a debounced API: part and set numbers use a "starts with" search while names use substring matching. Categories/themes that contain no matching items are not shown.
## Main Window
The main panel displays details depending on the Directory selection. For a part selection, the UI shows the part number, name, a list of available element colors, and images for those elements. For a set selection, the UI shows the set number, name, and the set image. When a set is selected, the UI also presents editable user fields (quantity and remark) persisted to the `user_sets` table.
Images for the selected elements are fetched in a background thread by `BackgroundImageFetcher` (in `view/image_loader.py`) and delivered to the UI via a `queue.Queue`. The UI polls the queue using a `QTimer` and updates the image area as results arrive. The UI cancels and joins any previous fetcher when the selection changes.
# Security
Treat external files (downloads from Rebrickable or files opened by the user) as untrusted. The codebase defends against SQL injection by:
- validating identifiers used to build SQL statements (see `model.db.sanitize_identifier`),
- using parameterized queries for data values,
- avoiding concatenation of untrusted strings into SQL statements.
Additionally, the code restricts synchronization URLs to approved prefixes and supports a developer-only dev-server mode for local testing.
