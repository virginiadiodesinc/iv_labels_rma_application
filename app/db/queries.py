from sqlalchemy import select

# CREATE
def add_table_entry(db_session, model, **data):
	try:
		#print("making entry")
		entry = model(**data)
		#print("adding entry")
		db_session.add(entry)
		#print("committing entry")
		db_session.commit()
		#print("refreshing DB with entry")
		db_session.refresh(entry)
		#print("returning entry")
		return entry
	except Exception as e:
		db_session.rollback()

		print(type(e))
		print(e)
		
		raise

# READ
def get_table_entries(db_session, model, **filters):
	query = select(model)
	for attribute, value in filters.items():
		if hasattr(model, attribute):
			query = query.where(getattr(model, attribute) == value)

	print(query)

	try:		
		entries = db_session.execute(query).scalars().all()
		print("query success")
		print(entries)
		return(entries)
	
	except Exception as e:
		print("query failed")
		print(type(e))
		print(e)

		raise

# UPDATE
def update_table_entry(db_session, model, entry_id, **updates):
	entry = db_session.get(model, entry_id)
	if not entry:
		print("no entry found")
		return False
	
	for key, value in updates.items():
		print("adding updates")
		if hasattr(entry, key):
			setattr(entry, key, value)
	print("comitting to db")
	db_session.commit()
	print("refreshing db")
	db_session.refresh(entry)

	return entry

# DESTROY
def delete_table_entry(db_session, model, entry_id):
	entry = db_session.get(model, entry_id)
	if not entry:
		return False
	
	db_session.delete(entry)
	db_session.commit()
	
	return True
