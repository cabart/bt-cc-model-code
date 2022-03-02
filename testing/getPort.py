import re

f = open("./rspecString.txt","r")
rspecString = f.read()
f.close()

pattern = re.compile("port=\"[0-9]+\"")
matches = pattern.findall(rspecString)
print("matches:", matches)

numberPattern = re.compile("[0-9]+")
for i in matches:
    print(numberPattern.findall(i))
