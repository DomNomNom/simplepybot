#position of name
name=1

#dictionary of names storing the id's of each name
name_dictionary=dict()

#list of quotes, location in the list is the quotes id number
quote_list=[]

#list of unused_id's, this corresponds to spaces left in the quote_list from deletions, adding
#quotes should prefer to fill these first
unused_id_list=[]

def initalise(filename):
  #local variables
  global name
  f=open(filename)
  lines=f.readlines()
  
  #loop through the file and read and parse each line adding it to the appropriate lists
  count=0
  while f.readable():
    line=parseLine(f)
    if line:
      add_name_mapping(line[name])
      add_quote(line, False)
     
    else:
      add_unused_id(count)

    count++

#if the given name exists in the dictionary then add that name->list_id mapping, if it doesn't then
#add the name to the dictionary and set up its id list with the given list_id
add_name_mapping(name, list_id):
  global name_dictionary
  if name in name_dictionary:
    name_dictionary[name].append(list_id)
  else:
    name_dictionary[name]=[list_id]

  return true

#add the unused_id to the global unused_id's list
add_unused_id(unused_id):
  global unused_id_list
  unused_id_list.append(unused_id)
  return true

#get an unused_id, method returns None if no id's are spare
get_unused_id():
  global unused_id_list
  if len(unused_id_list)>0:
    return unused_id_list.pop(1)
  else:
    return None

#add a quote to the global quote_list, if use_unused_id is false then it will not attempt to fill
#empty spaces in the quote_list
add_quote(quote, use_unused_id=True):
  global quote_list
  spare_id=None
  if use_unused_id:
    #attempt to grab any unused ID's in the quote_list
    spare_id=get_unused_id()

  if spare_id:
    #fill the unused space and return it's id
    quote_list[spare_id]=quote
    return spare_id
  
  else:
    #append quote to end of quote list and return it's id
    quote_list.append(quote)
    return len(quote_list)-1

#set the quote linked to quote_id to none and return the old quote to the caller
remove_quote(quote_id):
  global quote_list
  old_quote=quote_list[quote_id]
  quote_list[quote_id]=None
  add_unused_id(quote_id)
  return old_quote
