"""Extracts the correct revision number from every entry in VDI-547 and generates a new text file with engraving and tab-separated revision number"""
import re

revision_pattern = re.compile(r'(?<!(?<![a-zA-Z0-9])W)R\d(\.\d)?')
multi_pattern = re.compile(r'R\d(?:\.\d)?')

"""The following three lists can be used for troubleshooting"""
no_match_list = []
one_match_list = []
multi_match_list = []

engraving_revision_list = []

with open('VDI-547 Block Name List.txt', 'r', encoding='utf-8') as file:
    for line in file:
        if line[-1] == "\n":
                line = line[:-1]
        count = len(re.findall(revision_pattern, line))

        if count == 0:
            no_match_list.append(line)
            engraving_revision_list.append(line+"\tN/A\n")
        elif count == 1:
            one_match_list.append(line)
            engraving_revision_list.append(line+"\t"+re.search(revision_pattern, line).group()+"\n")
        else:
            multi_match_list.append(line)
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
            if pattern.search(line) != None and line[:-len(pattern.search(line).group())] != previous_line:
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
            elif pattern.search(line) != None and line[:-len(pattern.search(line).group())] == previous_line:
                counter = 0
                break
            elif pattern.search(line) == None:
                counter += 1
            
            if counter == 16:
                unique_build_list.append(line+"\n")
                counter = 0 

with open('unique_builds.txt', 'w') as file:
    for item in unique_build_list:
        file.write(f"{item}")