"""Extracts the correct revision number from every entry in VDI-547 and unique build in VDI-548 and generates new text files"""
import re

revision_pattern = re.compile(r'(?<!(?<![a-zA-Z0-9])W)R\d(\.\d)?') #find unpreceded standalone W and do not match an R if it is preceded by an unpreceded standalone W
multi_pattern = re.compile(r'R\d(?:\.\d)?') #find R#.# but do not create a separate capture group for the optional .#
swg_length_pattern = re.compile(r'SWG(\d)')
swgmd_length_pattern = re.compile(r'SWGMD(\d)')
twg_length_pattern = re.compile(r'TWG(\d)')
ewg_length_pattern = re.compile(r'EWG(\d)')
V_revision_pattern = re.compile(r'V\d$')
X_revision_pattern = re.compile(r'(?<!(QWE|4HM))X\d$')
XwVd_revision_pattern = re.compile(r'X\wV\d$')
Xd__revision_pattern = re.compile(r'(X\d)_\(')

WRdX_exception_pattern = re.compile(r'WR\d\d?\.?\d?\d?X\d$')

"""The following three lists can be used for troubleshooting"""
no_match_list = []
one_match_list = []
multi_match_list = []

engraving_revision_list = []

with open('VDI-547 Block Name List.txt', 'r', encoding='utf-8') as file:
    for line in file:
        if line[-1] == "\n":
                line = line[:-1]
        R_count = len(re.findall(revision_pattern, line))
        V_count = len(re.findall(V_revision_pattern, line))
        X_count = len(re.findall(X_revision_pattern, line))
        XwVd_count = len(re.findall(XwVd_revision_pattern, line))
        Xd__count = len(re.findall(Xd__revision_pattern, line))

        if R_count == 0 and V_count == 0 and X_count == 0 and XwVd_count == 0 and Xd__count == 0:
            if "SWG" in line and "SWGMD" not in line:
                if swg_length_pattern.search(line) is None:
                    engraving_revision_list.append(line+"\t1N\n") #1 inch No revision number
                elif swg_length_pattern.search(line) is not None:
                    engraving_revision_list.append(line+"\t"+swg_length_pattern.search(line).group(1)+"N\n") #length No revision number
            elif "SWGMD" in line:
                if swgmd_length_pattern.search(line) is None:
                    engraving_revision_list.append(line+"\t1N\n") #1 inch No revision number
                elif swgmd_length_pattern.search(line) is not None:
                    engraving_revision_list.append(line+"\t"+swgmd_length_pattern.search(line).group(1)+"N\n") #length plus R1
            elif "TWG" in line:
                if twg_length_pattern.search(line) is None:
                    engraving_revision_list.append(line+"\t1N\n") #1 inch No revision number
                elif twg_length_pattern.search(line) is not None:
                    engraving_revision_list.append(line+"\t"+twg_length_pattern.search(line).group(1)+"N\n") #length plus R1
            elif "EWG" in line:
                if ewg_length_pattern.search(line) is None:
                    engraving_revision_list.append(line+"\t1N\n") #1 inch No revision number
                elif ewg_length_pattern.search(line) is not None:
                    engraving_revision_list.append(line+"\t"+ewg_length_pattern.search(line).group(1)+"N\n") #length plus R1
            else:
                engraving_revision_list.append(line+"\tN\n")

        elif R_count == 1:
            if "SWG" in line and "SWGMD" not in line:
                if swg_length_pattern.search(line) is None:
                    engraving_revision_list.append(line+"\t1"+re.search(revision_pattern, line).group()+"\n") #1 inch plus Revision number
                elif swg_length_pattern.search(line) is not None:
                    engraving_revision_list.append(line+"\t"+swg_length_pattern.search(line).group(1)+re.search(revision_pattern, line).group()+"\n") #length plus Revision number
            elif "SWGMD" in line:
                if swgmd_length_pattern.search(line) is None:
                    engraving_revision_list.append(line+"\t1"+re.search(revision_pattern, line).group()+"\n") #1 inch plus Revision number
                elif swgmd_length_pattern.search(line) is not None:
                    engraving_revision_list.append(line+"\t"+swgmd_length_pattern.search(line).group(1)+re.search(revision_pattern, line).group()+"\n") #length plus Revision number
            elif "TWG" in line:
                if twg_length_pattern.search(line) is None:
                    engraving_revision_list.append(line+"\t1"+re.search(revision_pattern, line).group()+"\n") #1 inch plus Revision number
                elif twg_length_pattern.search(line) is not None:
                    engraving_revision_list.append(line+"\t"+twg_length_pattern.search(line).group(1)+re.search(revision_pattern, line).group()+"\n")
            elif "EWG" in line:
                if ewg_length_pattern.search(line) is None:
                    engraving_revision_list.append(line+"\t1"+re.search(revision_pattern, line).group()+"\n") #1 inch plus Revision number
                elif ewg_length_pattern.search(line) is not None:
                    engraving_revision_list.append(line+"\t"+ewg_length_pattern.search(line).group(1)+re.search(revision_pattern, line).group()+"\n")
            else:
                engraving_revision_list.append(line+"\t"+re.search(revision_pattern, line).group()+"\n")

        elif V_count == 1 and XwVd_count == 0: #this case does not apply to waveguides
            engraving_revision_list.append(line+"\t"+re.search(V_revision_pattern, line).group()+"\n")

        elif XwVd_count == 1: #this case does not apply to waveguides
            engraving_revision_list.append(line+"\t"+re.search(XwVd_revision_pattern, line).group()+"\n")

        elif X_count == 1:
            if WRdX_exception_pattern.search(line) is not None:
                engraving_revision_list.append(line+"\tN\n")
            elif "SWG" in line and "SWGMD" not in line:
                if swg_length_pattern.search(line) is None:
                    engraving_revision_list.append(line+"\t1"+re.search(X_revision_pattern, line).group()+"\n")
                elif swg_length_pattern.search(line) is not None:
                    engraving_revision_list.append(line+"\t"+swg_length_pattern.search(line).group(1)+re.search(X_revision_pattern, line).group()+"\n")
            elif "SWGMD" in line:
                if swgmd_length_pattern.search(line) is None:
                    engraving_revision_list.append(line+"\t1"+re.search(X_revision_pattern, line).group()+"\n")
                elif swgmd_length_pattern.search(line) is not None:
                    engraving_revision_list.append(line+"\t"+swgmd_length_pattern.search(line).group(1)+re.search(X_revision_pattern, line).group()+"\n")
            elif "TWG" in line:
                if twg_length_pattern.search(line) is None:
                    engraving_revision_list.append(line+"\t1"+re.search(X_revision_pattern, line).group()+"\n")
                elif twg_length_pattern.search(line) is not None:
                    engraving_revision_list.append(line+"\t"+twg_length_pattern.search(line).group(1)+re.search(X_revision_pattern, line).group()+"\n")
            elif "EWG" in line:
                if ewg_length_pattern.search(line) is None:
                    engraving_revision_list.append(line+"\t1"+re.search(X_revision_pattern, line).group()+"\n")
                elif ewg_length_pattern.search(line) is not None:
                    engraving_revision_list.append(line+"\t"+ewg_length_pattern.search(line).group(1)+re.search(X_revision_pattern, line).group()+"\n")
            else:
                engraving_revision_list.append(line+"\t"+re.search(X_revision_pattern, line).group()+"\n")

        elif Xd__count == 1:
            if "SWG" in line and "SWGMD" not in line:
                if swg_length_pattern.search(line) is None:
                    engraving_revision_list.append(line+"\t1"+re.search(Xd__revision_pattern, line).group(1)+"\n")
                elif swg_length_pattern.search(line) is not None:
                    engraving_revision_list.append(line+"\t"+swg_length_pattern.search(line).group(1)+re.search(Xd__revision_pattern, line).group(1)+"\n")
            elif "SWGMD" in line:
                if swgmd_length_pattern.search(line) is None:
                    engraving_revision_list.append(line+"\t1"+re.search(Xd__revision_pattern, line).group(1)+"\n")
                elif swgmd_length_pattern.search(line) is not None:
                    engraving_revision_list.append(line+"\t"+swgmd_length_pattern.search(line).group(1)+re.search(Xd__revision_pattern, line).group(1)+"\n")
            elif "TWG" in line:
                if twg_length_pattern.search(line) is None:
                    engraving_revision_list.append(line+"\t1"+re.search(Xd__revision_pattern, line).group(1)+"\n")
                elif twg_length_pattern.search(line) is not None:
                    engraving_revision_list.append(line+"\t"+twg_length_pattern.search(line).group(1)+re.search(Xd__revision_pattern, line).group(1)+"\n")
            elif "EWG" in line:
                if ewg_length_pattern.search(line) is None:
                    engraving_revision_list.append(line+"\t1"+re.search(Xd__revision_pattern, line).group(1)+"\n")
                elif ewg_length_pattern.search(line) is not None:
                    engraving_revision_list.append(line+"\t"+ewg_length_pattern.search(line).group(1)+re.search(Xd__revision_pattern, line).group(1)+"\n")
            else:
                engraving_revision_list.append(line+"\t"+re.search(Xd__revision_pattern, line).group(1)+"\n")

        else:
            #excluding SWG conditional since no SWG engravings have multiple instances of R occurring
            print(line)
            print("R_Count:"+str(R_count))
            print("V_Count:"+str(V_count))
            print("X_Count:"+str(X_count))
            print("XwVd_Count:"+str(XwVd_count))
            print("Xd__Count:"+str(Xd__count))
            engraving_revision_list.append(line+"\t"+re.findall(multi_pattern, line)[-1]+"\n")
    
with open('engraving_with_revision.txt', 'w') as file:
    for item in engraving_revision_list:
        file.write(f"{item}")

N_pattern = re.compile(r'_N$',re.IGNORECASE)
R_pattern = re.compile(r'_R\d+(\.\d)?\w?$',re.IGNORECASE)
X_pattern = re.compile(r'_X\d+(\.\d)?$',re.IGNORECASE)
C_pattern = re.compile(r'_C$',re.IGNORECASE)
V_pattern = re.compile(r'_V\d+(\.\d)?$')
WG_N_pattern = re.compile(r'_\dN$',re.IGNORECASE)
WG_R_pattern = re.compile(r'_\dR\d+(\.\d)?$',re.IGNORECASE)
WG_X_pattern = re.compile(r'_\dX\d+(\.\d)?$',re.IGNORECASE)
WG_MD_R_pattern = re.compile(r'_MD\dR\d+(\.\d)?$',re.IGNORECASE)
ISAXR_pattern = re.compile(r'_ISAXR\d(\.\d)?$',re.IGNORECASE)
QHMR_pattern = re.compile(r'_QHMR\d+(\.\d)?$')
QR_pattern = re.compile(r'_QR\d+(\.\d)?$',re.IGNORECASE)
R_X_pattern = re.compile(r'_R\d+(\.\d)?-?X\d$',re.IGNORECASE)
FDR_pattern = re.compile(r'_FDR\d+(\.\d)?$',re.IGNORECASE)
R_C_pattern = re.compile(r'_R\d+(\.\d)?-C$',re.IGNORECASE)
N_R_pattern = re.compile(r'_N-?_?R\d+(\.\d)?$', re.IGNORECASE)

pattern_list = [
    WG_MD_R_pattern,
    WG_N_pattern,
    WG_R_pattern,
    WG_X_pattern,
    QR_pattern,
    R_X_pattern,
    FDR_pattern,
    R_C_pattern,
    N_R_pattern,
    N_pattern,
    R_pattern,
    X_pattern,
    C_pattern,
    V_pattern,
    ISAXR_pattern,
    QHMR_pattern
]

unique_build_list = []
counter = 0

with open('VDI-548 Build Name List.txt', 'r', encoding='utf-8') as file:
    previous_line = ''
    for line in file:
        if line[-1] == "\n":
            line = line[:-1]
            if "VDI6.5X6SHMG4-I-N_R8" in line: #stupid exception
                print(repr(line))
                line = line[:-1]
        for pattern in pattern_list:
            if pattern.search(line) is not None and line[:-len(pattern.search(line).group())] != previous_line:
                unique_build_list.append(line[:-len(pattern.search(line).group())]+"\n")
                previous_line = line[:-len(pattern.search(line).group())]
                """
                if pattern_list[counter] in pattern_list[3:6]:
                    unique_build_list.append(line[:-(len(pattern.search(line).group()) - 2)]+"\n")
                    previous_line = line[:-(len(pattern.search(line).group()) - 2)]
                elif pattern_list[counter] == pattern_list[6]:
                    unique_build_list.append(line[:-(len(pattern.search(line).group()) - 4)]+"\n")
                    previous_line = line[:-(len(pattern.search(line).group()) - 4)]
                else:
                    unique_build_list.append(line[:-len(pattern.search(line).group())]+"\n")
                    previous_line = line[:-len(pattern.search(line).group())]    
                """
                counter = 0
                break
            elif pattern.search(line) is not None and line[:-len(pattern.search(line).group())] == previous_line:
                counter = 0
                break
            elif pattern.search(line) is None:
                counter += 1
            
            if counter == 16:
                unique_build_list.append(line+"\n")
                counter = 0 

with open('unique_builds.txt', 'w') as file:
    for item in unique_build_list:
        file.write(f"{item}")