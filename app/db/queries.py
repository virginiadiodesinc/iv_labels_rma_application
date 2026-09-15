from sqlalchemy import select, delete

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
def get_table_entries(db_session, model, **filters):
	query = select(model)
	for attribute, value in filters.items():
		if hasattr(model, attribute):
			query = query.where(getattr(model, attribute) == value)
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
	print(data)
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