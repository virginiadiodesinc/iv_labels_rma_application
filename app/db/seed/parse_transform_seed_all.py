from app.db.seed import bootstrap_block_checkpoint, bootstrap_build_checkpoint, bootstrap_iv_checkpoint
from app.db.seed import parse_block_files, parse_build_files, parse_iv_files
from app.db.seed import transform_block_records, transform_build_records, transform_iv_records
from app.db.seed import seed_block_info, seed_build_info, seed_iv_info


bootstrap_block_checkpoint.main()
bootstrap_build_checkpoint.main()
bootstrap_iv_checkpoint.main()

parse_block_files.main()
transform_block_records.main()
seed_block_info.main()

parse_build_files.main()
transform_build_records.main()
seed_build_info.main()

parse_iv_files.main()
transform_iv_records.main()
seed_iv_info.main()


