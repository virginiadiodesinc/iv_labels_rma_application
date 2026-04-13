import pyodbc
import re

def get_Build_Name_List(user_input):
    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 18 for SQL Server};'
        'SERVER=10.1.10.31,1433;'
        'DATABASE=VDI-JB2;'
        'UID=python;'
        r'PWD=3s0brK09%iPS$6o9^h%W;'
        'Encrypt=yes;TrustServerCertificate=yes;'
    )

    cursor = conn.cursor()

    sql_build_name_query =  "SELECT DISTINCT " \
                            "   Estim.PartNo " \
                            "FROM " \
                            "   Estim " \
                            "WHERE " \
                            "   (Estim.Descrip LIKE '%COMPONENT:%' OR Estim.Descrip LIKE '%ATTENUATOR:%') AND" \
                            "   Estim.PartNo LIKE '%"+user_input+"%';"
                            

    cursor.execute(sql_build_name_query)

    parts_found = []

    for row in cursor.fetchall():
        parts_found.append(row)

    # print(parts_found)

    return parts_found

def get_BOM(build_name):
    category_pattern = re.compile(r'^([\w, ]*):')

    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 18 for SQL Server};'
        'SERVER=10.1.10.31,1433;'
        'DATABASE=VDI-JB2;'
        'UID=python;'
        r'PWD=3s0brK09%iPS$6o9^h%W;'
        'Encrypt=yes;TrustServerCertificate=yes;'
    )

    cursor = conn.cursor()

    sql_BOM_query =     "SELECT " \
                        "   Materials.SubPartNo, " \
                        "   Materials.Descrip, " \
                        "   Materials.ItemNo, " \
                        "   Materials.Qty, " \
                        "   Materials.Materials_ID " \
                        "FROM " \
                        "   Materials " \
                        "INNER JOIN Estim " \
                        "   ON Materials.PartNo = Estim.PartNo " \
                        "WHERE " \
                        "   Materials.PartNo LIKE '"+build_name+"';"

    cursor.execute(sql_BOM_query)

    BOM = []

    Passive_Multiplier_Doubler_Patterns = [ #VDI-712 Table 1, 1st division
        r'^VDI\d\d\d?(X2|X4|X6)(?!.*HM)', #Varactor doubler build names, all frequencies
        r'^VDI\d\d?\.\d\d?(X2|X4|X6)(?!\d{1,})(?!.*HM)' #Varistor doubler build names, all frequencies
    ]
    Passive_Multiplier_Tripler_Patterns = [ #VDI-712 Table 1, 2nd division
        r'^VDI\d\d\d?\d?(X3|X5|X9)(?!.*HM)', #Varactor tripler build names, all frequencies
        r'^VDI\d\d?\.\d\d?(X3|X5|X9)(?!\d{1,})(?!.*HM)' #Varistor tripler build names, all frequencies
    ]
    Discrete_Mixer_and_Detector_Patterns = [ #VDI-712 Table 2
        r'^VDI\d\d?.\d\d?.*(HM|BAM|ZBD|FM|DD|HPM|FSF-MIX|NS)', #Discrete mixers, detectors, noise sources, all frequencies
        r'^VDIQOD' #QOD parts
    ]
    ITX_and_IAMC_Patterns = [ #VDI-712 Table 3, 1st division
        r'^VDI\d\d\dIAMC', #VDI IAMC build names, non WR format
        r'^VDI\d\d?\.\d\d?IAMC', #VDI IAMC build names, WR format
        r'^VDI\d\d\dITX' #ITX build names, all frequencies
    ]
    XnSHM_and_MixAMC_I_and_RAD_Patterns = [ #VDI-712 Table 3, 2nd division
        r'^VDI\d\d?\.\d\d?X\d\d?(Q|S)H(B|M)', #Integrated varistor components, all frequencies
        r'^VDI\d\d?\.\d\d?RAD', #RAD build names, WR format
        r'^VDI\d\d\dRAD', #RAD build names, non WR format
        r'^VDI\d\d\dPOLMTR' #POLMTR builds, all frequencies
    ]
    VDI_AMP_Patterns = [ #VDI-712 Table 3, 3rd division AMPs and LNAs
        r'^VDI\d\d?\.\d\d?AMP', 
        r'^VDI\d\d\d?AMP',
        r'^VDIPOLSIR-LNA',
        r'^VDIWR\d\d?\.\d\d?AMP'
    ]
    VDIC_Patterns = [ #VDI-712 Table 4, 1st division
        r'^VDIC' #VDIC builds, all frequencies
    ]
    Miscellaneous_Patterns = [ #VDI-712 Table 4, 2nd division
        r'^VDI\d\d?\.\d\d?SWG-PL', #Load waveguides, all frequencies
        r'^VDIRW3600SWG-PL', #One off load
        r'^VDI\d\d?\.\d\dBPFE', #Bandpass filters, all frequencies
        r'^VDI-LPF', #Coaxial filters, all frequencies
        r'^VDI\d\d?\.\d\d?X1$', #HRF builds, all frequencies
        r'^VDI\d\d?\.\d\d?BC3', #3 port couplers, all frequencies
        r'^VDI\d\d?\.\d\d?DC', #DC couplers, all frequencies
        r'^VDI\d\d?\.\d\d?E?BC4P', #4 port couplers, all frequencies
        r'^VDI\d\d?\.\d\d?SWG\d-\d\d?', #waveguide attenuators, all frequencies
        r'^VDI\d\d?\.\d\d?SWG-LD', #waveguide loads, all frequencies
        r'VDI\d\d?\.\d\d?MVA' #variable attenuators, all frequencies
    ]

    for row in cursor.fetchall():
        if 'CDMCOST' not in row[0]:
            category = re.search(category_pattern, row[1]).group(1)
            bom_entry = {"part_name": row[0], "part_quantity": row[3], "part_type": category, "part_lot": ""}
            BOM.append(bom_entry)
            #BOM.append([row[0], row[3], category]) #List of parts on BOM, their quantity, and their category
        else:
            continue

    #print(BOM)

    return BOM
    
def get_Lots_from_list(BOM_input):
    Lots = {}
    Lots_list = []

    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 18 for SQL Server};'
        'SERVER=10.1.10.31,1433;'
        'DATABASE=VDI-JB2;'
        'UID=python;'
        r'PWD=3s0brK09%iPS$6o9^h%W;'
        'Encrypt=yes;TrustServerCertificate=yes;'
    )

    cursor = conn.cursor()

    for subpart in BOM_input:

        sql_lots_query =     "SELECT DISTINCT " \
                            "   ReceiverDet.LotNo " \
                            "FROM " \
                            "   ReceiverDet " \
                            "INNER JOIN Materials " \
                            "   ON ReceiverDet.PartNo = Materials.SubPartNo " \
                            "WHERE " \
                            "   Materials.SubPartNo LIKE '"+subpart[0]+"' AND " \
                            "   ReceiverDet.LotNo NOT LIKE '' AND " \
                            "   ReceiverDet.LotNo NOT LIKE '<Multiple>' AND " \
                            "   ReceiverDet.LotNo IS NOT NULL;"
         
        cursor.execute(sql_lots_query)

        for row in cursor.fetchall():
            Lots_list.append(row)
        
        Lots[subpart[0]] = Lots_list
        Lots_list = []

    #print(Lots)

    return Lots

def get_Lots(BOM_input):

    Lots = []

    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 18 for SQL Server};'
        'SERVER=10.1.10.31,1433;'
        'DATABASE=VDI-JB2;'
        'UID=python;'
        r'PWD=3s0brK09%iPS$6o9^h%W;'
        'Encrypt=yes;TrustServerCertificate=yes;'
    )

    cursor = conn.cursor()

    sql_lots_query =    "SELECT DISTINCT " \
                        "   ReceiverDet.LotNo " \
                        "FROM " \
                        "   ReceiverDet " \
                        "INNER JOIN Materials " \
                        "   ON ReceiverDet.PartNo = Materials.SubPartNo " \
                        "WHERE " \
                        "   Materials.SubPartNo LIKE '"+BOM_input+"' AND " \
                        "   ReceiverDet.LotNo NOT LIKE '' AND " \
                        "   ReceiverDet.LotNo NOT LIKE '<Multiple>' AND " \
                        "   ReceiverDet.LotNo IS NOT NULL;"
         
    cursor.execute(sql_lots_query)

    for row in cursor.fetchall():
        Lots.append(row[0])

    #print(Lots)

    return Lots