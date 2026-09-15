from app.db.seed import parse_block_files, parse_build_files, parse_iv_files
from app.db.seed import transform_block_records, transform_build_records, transform_iv_records
from app.db.seed import seed_block_info, seed_build_info, seed_iv_info

parse_block_files.main()
transform_block_records.main()
seed_block_info.main()

parse_build_files.main()
transform_build_records.main()
seed_build_info.main()

parse_iv_files.main()
transform_iv_records.main()
seed_iv_info.main()


