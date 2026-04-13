from sqlalchemy import select

# CREATE
def add_table_entry(db_session, model, **data):
	entry = model(**data)
	db_session.add(entry)
	db_session.commit()
	db_session.refresh(entry)
	
	return entry

# READ
def get_table_entries(db_session, model, **filters):
	query = select(model)
	for attribute, value in filters.items():
		if hasattr(model, attribute):
			query = query.where(getattr(model, attribute) == value)
			
	entries = db_session.execute(query).scalars().all()
	return entries

# UPDATE
def update_table_entry(db_session, model, entry_id, **updates):
	entry = db_session.get(model, entry_id)
	if not entry:
		return False
	
	for key, value in updates.items():
		if hasattr(entry, key):
			setattr(entry, key, value)
			
	db_session.commit()
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
