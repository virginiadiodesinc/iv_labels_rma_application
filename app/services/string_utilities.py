# PART_A_LOT12345
# PART_A LOT12345
# PART_A LOT 12345
# PART_A LOT#12345
# PART_A #12345
# PART_ALOT12345
# PART_A_LOT#12345
# PART_A
# PART_A_123214 - TOO TRICKY, JUST SEND AS FULL PART NAME

# 3 MAIN CASES
# 1) NO LOT AT ALL - VERY SIMPLE, LOT IS EMPTY STRING
# 2) THE WORD 'LOT' USED BETWEEN PART AND LOT - SEPARATE PART BEFORE AND LOT AFTER
# 3) THE WORD 'LOT' IS NOT USED BETWEEN PART AND LOT - EITHER VIA AN UNDERSCORE OR WHITESPACE

# SUBCASES
# '#', ':', '(', ')' CAN BE REMOVED
# '_' CAN EXIST INSIDE A PART NUMBER OR AS THE SEPARATOR BETWEEN PARTS AND LOTS
# ' ' IS THE MOST COMMON SEPARATOR
import pandas as pd

def separate_part_and_lot(part_and_lot_text):
	part_and_lot_text = part_and_lot_text.upper()
	part = ""
	lot = ""
	extra = ""
	split_text = []

	# IF EMPTY STRING (OR JUST WHITESPACE)
	if len(part_and_lot_text.split()) == 0:
		return part, lot, extra

	# TRY TO SPLIT VIA WORD 'LOT'
	if "LOT" in part_and_lot_text:
		split_text = part_and_lot_text.split('LOT')

	# IF THAT FAILS, SPLIT ON WHITESPACE
	else:
		split_text = part_and_lot_text.split()

	# STRIP ALL NON-ALPHANUMERIC CHARACTERS OFF END OF PART AND BEGINNING OF LOT
	if len(split_text) > 1:
		part_full_text = split_text[0]
		lot_full_text = split_text[1]

		if len(part_full_text) > 1:
			while not part_full_text[-1].isalnum():
				part_full_text = part_full_text[:-1]

		if len(lot_full_text) > 1:
			while not lot_full_text[0].isalnum():
				lot_full_text = lot_full_text[1:]

			if len(lot_full_text.split()) > 1:
				extra = "".join(lot_full_text.split()[1:])
				lot_full_text = lot_full_text.split()[0]

		part = part_full_text
		lot = lot_full_text
	else:
		part = split_text[0]
		lot = ""

	return part, lot, extra

def separate_serial_number_and_revision(serial_number_and_revision_text):
	serial_number = ""
	revision = ""

	if serial_number_and_revision_text[-1].isalpha():
		revision = serial_number_and_revision_text[-1]
		serial_number = serial_number_and_revision_text[:-1]
	else:
		revision = "A"
		serial_number = serial_number_and_revision_text

	return serial_number, revision

def custom_lot_handler(parts_list, lots_list, custom_lots_list):
	custom_index = 0
	for index, lot in enumerate(lots_list):
		if lot == "Other":
			lots_list[index] = custom_lots_list[custom_index]
			custom_index += 1
	return lots_list

def get_build_name_with_suffix(build_name, block_engraving):
	block_engraving_df_columns = ["Block_Engraving", "Build_Suffix"]
	block_engraving_df = pd.read_csv('app/services/block_engravings.csv', names=block_engraving_df_columns, index_col=False)

	if any(block_engraving_df.loc[block_engraving_df["Block_Engraving"] == block_engraving, "Build_Suffix"]):
		build_revision_suffix = block_engraving_df.loc[block_engraving_df["Block_Engraving"] == block_engraving, "Build_Suffix"].values[0]
	else:
		build_revision_suffix = "unknown"

	build_name_with_suffix = build_name + "_" + build_revision_suffix

	return build_name_with_suffix

def main():
	random_part_list = [
	"A4APED11.5FGXXX_LOT1111",
	"WR6.5X2SHMPCBR1(Lot#20231019 R2 = 392ohm",
	"WR6.5SHMPCBR2   LOT#: 20240312",
	"WR8.0LNABBPCBR1 Lot 20260603",
	"WR10IAMCHPPCBR12Lot20260129",
	"210X2_2510-198G_AL121-Z1.5D",
	"175X2_REV_201502_12345"
	]

	random_serial_list = [
		"3-01",
		"01-999",
		"2-02B",
		"4-05AA"
	]
	
	for text in random_part_list:
		part, lot, extra = separate_part_and_lot(text)
		print("Part: ", part)
		print("Lot: ", lot)
		print("Extra: ", extra)
	
	for text in random_serial_list:
		serial_number, revision = separate_serial_number_and_revision(text)
		print("Serial Number: ", serial_number)
		print("Revision: ", revision)

	return


if __name__ == "__main__":
	main()
	