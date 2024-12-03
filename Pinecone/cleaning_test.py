import re


def remove_tags(text):
    # Remove HTML-like tags
    text = re.sub(r"</?\s*\w+(?:\s*[^>]*)?>", "", text)
    # Remove chunks surrounded by {[ ]}
    text = re.sub(r"\{\[.*?\]\}", "", text)
    # Remove numbers
    text = re.sub(r"\b\d+\b", "", text)
    # Remove individual letters
    text = re.sub(r"\b[a-zA-Z]\b", "", text)
    # Remove URLs and links
    text = re.sub(r"\bhttps?://\S+|localhost:\S+\b", "", text)
    # Remove concatenated stopwords like is/are, and/or
    text = re.sub(r"\b\w+/\w+\b", "", text)
    return text.strip()


def remove_tags_and_stopwords(text):
    # Remove HTML-like tags
    text = re.sub(r"</?\s*\w+(?:\s*[^>]*)?>", "", text)
    # Path to stopwords file
    stopwords_file = "../english.txt"
    # Remove chunks surrounded by {[ ]}
    text = re.sub(r"\{\[.*?\]\}", "", text)
    # Remove numbers
    text = re.sub(r"\b\d+\b", "", text)
    # Remove individual letters
    text = re.sub(r"\b[a-zA-Z]\b", "", text)
    # Remove URLs and links
    text = re.sub(r"\bhttps?://\S+|localhost:\S+\b", "", text)
    # Remove concatenated stopwords like is/are, and/or
    text = re.sub(r"\b\w+/\w+\b", "", text)

    # Load stopwords
    with open(stopwords_file, 'r') as file:
        stopwords = set(word.strip().lower() for word in file.readlines())

    # Remove stopwords
    words = text.split()
    filtered_words = [word for word in words if word.lower() not in stopwords]
    text = ' '.join(filtered_words)

    return text.strip()



text = """
<HEADING (PAGE NUMBER = 2)>Safety Data Sheet< HEADING />
OU PONT {['TITLE EXTRACT']}
<HEADING (PAGE NUMBER = 2)>DuPont TM Matrix® SG Herbicide< HEADING />
Version 3.0
<TABLE EXTRACT (TABLE NUMBER = 1, PAGE NUMBER = 2)>
['Issue Date :', '03/18/2019']
['Revision Date :', '02/07/2019']
Table extracted to localhost:5151/DuPontMatrixSDS_1_table_1.png
<TABLE EXTRACT />
Ref. 130000043303
<TABLE EXTRACT (TABLE NUMBER = 2, PAGE NUMBER = 2)>
['Other Ingredients', '', '69 %']
['Present as an impurity in the clay component of this product:', '', '']
['Titanium dioxide', '13463-67-7', '0.1 - 0.5%']
Table extracted to localhost:5151/DuPontMatrixSDS_1_table_2.png
<TABLE EXTRACT />
The specific chemical identity and/or exact percentage (concentration) of composition has been withheld as a trade secret.
SECTION 4. FIRST AID MEASURES
<TABLE EXTRACT (TABLE NUMBER = 3, PAGE NUMBER = 2)>
['General advice', ': Have the product container or label with you when calling a poison control center or doctor, or going for treatment. For medical emergencies involving this product, call toll free 1-800-441-3637. See Label for Additional Precautions and Directions for Use. Information presented in Section 4 conforms to the requirements of the Occupational Safety and Health Administration (OSHA) Hazard Communication Standard of 2012. See Section 15 for applicable information conforming to the requirements of the Federal Insecticide Fungicide and Rodenticide Act (FIFRA), as required by the US Environmental Protection Agency (EPA), or by state Regulatory Agencies.']
['Inhalation', ': No specific intervention is indicated as the compound is not likely to be hazardous. Consult a physician if necessary.']
['Skin contact', ': Take off all contaminated clothing immediately. Rinse skin immediately with plenty of water for 15-20 minutes. Call a poison control center or doctor for treatment advice.']
['Eye contact', ': Hold eye open and rinse slowly and gently with water for 15-20 minutes. Remove contact lenses, if present, after the first 5 minutes, then continue rinsing eye. Call a poison control center or doctor for treatment advice.']
['Ingestion', ': No specific intervention is indicated as the compound is not likely to be hazardous. Consult a physician if necessary.']
['Most important symptoms/effects, acute and delayed', ': No applicable data available.']
['Protection of first-aiders', ': No applicable data available.']
['Notes to physician', ': No applicable data available.']
Table extracted to localhost:5151/DuPontMatrixSDS_1_table_3.png
<TABLE EXTRACT />
2/12
"""



if __name__ == "__main__":
    print(remove_tags_and_stopwords(text))
