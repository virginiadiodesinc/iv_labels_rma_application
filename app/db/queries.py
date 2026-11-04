from sqlalchemy import select, delete, func, cast, Integer, inspect

# All of CREATE/UPDATE/DESTROY/UPSERT below STAGE a change (add/setattr +
# flush) but never commit and never catch/rollback on their own. Committing
# or rolling back is the caller's call -- specifically, it should happen
# exactly ONCE per save, in the orchestrator, after every step of that save
# (DB stage, file write, whatever else) has succeeded. If any one of you
# raises, let it propagate -- the orchestrator's try/except is what decides
# whether to call roll_back_db_changes.


# CREATE
def add_table_entry(db_session, model, **data):
	entry = model(**data)
	db_session.add(entry)
	db_session.flush()   # assigns PKs/defaults, visible within this transaction, NOT committed
	return entry


# READ
def get_table_entries(db_session, model, limit=None, **conditions):
	query = select(model)
	for attribute, value in conditions.items():
		if hasattr(model, attribute):
			query = query.where(getattr(model, attribute) == value)

	if limit != None:
		result_limit = int(limit)
		query = query.limit(result_limit)
		
	return db_session.execute(query).scalars().all()


# READ (LIKE)
def get_table_entries_like(db_session, model, limit=None, **conditions):
	query = select(model)
	for attribute, value in conditions.items():
		if hasattr(model, attribute):
			query = query.where(getattr(model, attribute).startswith(value))

	if limit != None:
			result_limit = int(limit)
			query = query.limit(result_limit)
			
	return db_session.execute(query).scalars().all()


# UPDATE
def update_table_entry(db_session, model, entry_id, **updates):
	entry = db_session.get(model, entry_id)
	if not entry:
		return False

	for key, value in updates.items():
		if hasattr(entry, key):
			setattr(entry, key, value)
	db_session.flush()
	return entry


# DESTROY
def delete_table_entry(db_session, model, entry_id):
	entry = db_session.get(model, entry_id)
	if not entry:
		return False

	db_session.delete(entry)
	db_session.flush()
	return True


# UPSERT (ADD IF NEW, UPDATE IF NOT)
def upsert_table_entry(db_session, model, entry_id, **data):
	entry = db_session.get(model, entry_id)
	if not entry:
		entry = add_table_entry(db_session, model, **data)
	else:
		entry = update_table_entry(db_session, model, entry_id, **data)
	return entry


# COMMIT -- call exactly once, after every staged write for one save has succeeded
def commit_db_changes(db_session):
	db_session.commit()


# ROLL BACK -- discards everything staged (flushed but not committed) since the last commit
def roll_back_db_changes(db_session):
	db_session.rollback()

# ADVANCED QUERIES

# ---------- FILTERS ----------

def translate_filter(field, operation, value):
	"""One (column, op, value) -> one SQL condition object. Generic: doesn't
	know or care which column it was given."""
	if operation == "eq":
		return field == value
	elif operation == "gte":
		return field >= value
	elif operation == "lte":
		return field <= value
	elif operation == "lt":          # for the "up to and including this day" DateTime case
		return field < value
	elif operation == "starts_with":
		return field.startswith(value, autoescape=True)
	elif operation == "contains":
		return field.icontains(value, autoescape=True)
	elif operation == "in":
		return field.in_(value)
	raise ValueError(f"invalid operation: {operation}")


def build_filter_conditions(filters, registry):
	"""filters:  list of (key, operation, value) from the user
	registry: dict supplied by the caller, e.g.
	    {"serial": {"column": <col>, "ops": {"eq", "in"}, "coerce": str}}
	Returns a list of conditions. Validation lives here, once."""
	conditions = []
	for key, operation, value in filters:
		entry = registry.get(key)
		if entry is None:
			raise ValueError(f"unknown filter: {key}")
		if operation not in entry["ops"]:
			raise ValueError(f"'{operation}' not allowed for '{key}'")

		coerce = entry.get("coerce")
		if coerce:
			value = [coerce(v) for v in value] if operation == "in" else coerce(value)

		if "builder" in entry:       # custom: OR across columns, EXISTS, etc.
			conditions.append(entry["builder"](operation, value))
		else:
			conditions.append(translate_filter(entry["column"], operation, value))
	return conditions


def apply_filters(query, conditions):
	return query.where(*conditions) if conditions else query


# ---------- SORTS ----------

def translate_sort(keys, direction):
	"""keys: a LIST of expressions (one for a plain column, several for
	something like serial number). Direction and NULL placement are applied
	to every key."""
	if direction == "ascending":
		return [k.asc().nulls_last() for k in keys]
	elif direction == "descending":
		return [k.desc().nulls_last() for k in keys]
	raise ValueError(f"invalid direction: {direction}")


def build_sort_orderings(sorts, registry):
	"""sorts: ordered list of (key, direction). List position = priority.
	registry: {"serial": [expr, expr], "save_date": [expr]}"""
	orderings = []
	for key, direction in sorts:
		keys = registry.get(key)
		if keys is None:
			raise ValueError(f"unknown sort: {key}")
		orderings.extend(translate_sort(keys, direction))
	return orderings


def apply_sort(query, model, orderings):
	"""Appends the model's own primary key as a final ascending tiebreaker,
	so callers can't forget it and pagination stays stable."""
	tiebreakers = [col.asc() for col in inspect(model).primary_key]
	return query.order_by(*orderings, *tiebreakers)


# ---------- COUNT / PAGE ----------

def count_query(db_session, query):
	"""Count rows a query would return. Strips ORDER BY first (pointless for a count)."""
	counted = select(func.count()).select_from(query.order_by(None).subquery())
	return db_session.execute(counted).scalar_one()


def paginate(query, page, page_size):
	return query.limit(page_size).offset((page - 1) * page_size)