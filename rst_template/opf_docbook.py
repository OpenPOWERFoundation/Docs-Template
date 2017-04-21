#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Builds OpenPOWER Foundation documentation using standard template.
#
# Assumes rst2db has been used to convert rst to docbook.
#
import os, sys, getopt, shutil, errno
from lxml import etree
from conf import opf_docbook_settings, master_doc

def copy_xml_to_template(src_dir, tgt_dir):
    # Copy XML files
    src_files = os.listdir(src_dir)
    for filename in src_files:
        full_file = os.path.join (src_dir, filename)
        if (os.path.isfile(full_file)):
            shutil.copy(full_file, tgt_dir)
        elif (os.path.isdir(full_file)):
            try:
                os.makedirs(os.path.join(tgt_dir,filename))
            except OSError as exception:
                if exception.errno != errno.EEXIST:
                    raise
            copy_xml_to_template( os.path.join(src_dir,filename), os.path.join(tgt_dir,filename) )

def update_file(filename, old_str, new_str):    
    # Verify tag exists
    with open(filename) as f:
        s = f.read()
        if old_str not in s:
            print 'Error: "{old_str}" not found in {filename}.'.format(**locals())
            sys.exit(-2)

    # Safely write the changed content, if found in the file
    with open(filename, 'w') as f:
        s = s.replace(old_str, new_str)
        f.write(s)

def print_tree(element, level):
    # Print current element
    num_children = element.__len__()
    indent = ' '.ljust(level+1)
    print indent, 'Tag: ', element.tag, ' Attrib: ', element.attrib, ' Num children: ', num_children
    
    for i in range(num_children):
        child = element.__getitem__(i)
        print_tree(child, level+1)

def convert_top_level_sections(head, file):
    path = os.path.dirname(file)
    if 'sect' in head.tag:
        head.tag = 'book'
        
        # Clear attributes
        for attrib in head.attrib.keys():
            head.attrib.pop(attrib, None)
        if head.attrib.items() != []:
            print 'Error: Section attributes not removed. ', head.attrib.items(), ' items remain -- ', head.attrib.keys()
            sys.exit(-5)
        
        # Walk children to remove title    
        num_children = head.__len__()
        for i in range(num_children):
            child = head.__getitem__(i)
            if 'title' in child.tag:
                head.__delitem__(i)
                break
                
        # Walk children looking for next set of <section> tags, opening include files if necessary
        num_children = head.__len__()
        num_chapter = 0
        for i in range(num_children):
            child = head.__getitem__(i)
            
            # check for section tag
            if 'section' in child.tag:
                # Convert tag to <chapter>
                child.tag = child.tag.replace('section','chapter')
                num_chapter = num_chapter+1
                
            # check for include tag
            if 'include' in child.tag:
                # Open and parse include file
                # NOTE: We will only check one level deep
                include_file = child.attrib['href']
                full_include_file = os.path.join(path,include_file)
                parser = etree.XMLParser(remove_comments=False)    
                tree = etree.parse(full_include_file, parser=parser)
                #print_tree( tree.getroot(), 0 )
                
                # Check for sections
                include_head = tree.getroot()
                if 'sect' in include_head.tag:
                    # Convert tag to <chapter>
                    include_head.tag = include_head.tag.replace('section','chapter')
                    num_chapter = num_chapter+1
                    
                    # Create backup file
                    shutil.copy2(full_include_file, full_include_file+'.bak')
                    
                    # Write out changed file
                    tree.write(full_include_file)
        if num_chapter == 0:
            print 'Error: No chapters found in document'
            sys.exit(-6)
    else:
        print 'Toc file contains ', head.tag, 'tag, not <section>'
        sys.exit(-4)

def remove_book_tags(old_file, new_file):
    with open(old_file, 'r') as input:
        with open(new_file, 'wb') as output:
            for line in input:
                if '<book' not in line and '</book>' not in line:
                    output.write(line)

def insert_toc_into_book(toc_file, book_file):
    book_file_bak = book_file+'.bak'
    shutil.copy2(book_file, book_file_bak)
    key_string = '<!--TBD-->'
    inserted_toc = False

    with open(book_file_bak, 'r') as input:
        with open(book_file, 'wb') as output:
            for line in input:
                if key_string not in line:
                    output.write(line)
                else:
                    inserted_toc = True
                    # Write toc_file contents
                    with open(toc_file, 'r') as input_toc:
                        for line_toc in input_toc:
                            output.write(line_toc)    
    
    if not inserted_toc:
        print 'Error: key string of "', key_string, '" not found in ', book_file
        sys.exit(-7)
                        
def main(argv):
    build_dir = ''
    db_dir = ''
    master_dir = ''
    template_dir = ''
    toc_file = master_doc+'.xml'

    try:
        opts, args = getopt.getopt(argv,"hb:d:m:t:",["builddir=","docbookdir=","masterdir=","templatedir="])
    except getopt.GetoptError:
        print 'Invalid option specified.  Usage:'
        print '    opf_docbook.py -b <builddir> -d <docbookdir> -m <masterdir> -t <templatedir>'
        sys.exit(-1)
    for opt, arg in opts:
        if opt == '-h':
           print 'opf_docbook.py -b <builddir> -d <docbookdir> -m <masterdir> -t <templatedir>'
           sys.exit()
        elif opt in ("-b", "--builddir"):
           build_dir = arg
        elif opt in ("-d", "--docbookdir"):
           db_dir = arg
        elif opt in ("-m", "--masterdir"):
           master_dir = arg
        elif opt in ("-t", "--templatedir"):
           template_dir = arg

    # Locate the TOC file
    rst_template_dir = os.path.join(template_dir, 'rst_template') 
    full_toc_file = os.path.join(rst_template_dir,  toc_file)
    book_file = os.path.join(rst_template_dir,  'bk_main.xml')
    
    # Copy all files and directories in docbook dir into rst_template recursively
    copy_xml_to_template( db_dir, rst_template_dir) 

    # Update all file in opf_docbook_settings with tag/value combinations specified
    for f in opf_docbook_settings.keys():
        filename = os.path.join(rst_template_dir, f)
        tags = opf_docbook_settings[f]

        for tag in tags:
          value = opf_docbook_settings[f][tag]
          
          if value != '':
              new_str = '<'+tag+'>'+value+'</'+tag+'>'
          else:
              new_str = ''

          old_str = '<'+tag+'>TBD</'+tag+'>'
          update_file(filename, old_str, new_str)
    
    # Parse TOC file, convert high level tag to "book" and write back out to .tmp1 file
    parser = etree.XMLParser(remove_comments=False)    
    tree = etree.parse(full_toc_file, parser=parser)
    # print_tree( tree.getroot(), 0 )
    convert_top_level_sections( tree.getroot(), full_toc_file )
    full_toc_file_tmp1 = full_toc_file+'.tmp1'  
    tree.write(full_toc_file_tmp1)
    
    # Eliminate <book> and <title> tags in .tmp1 and write to .tmp2 file
    full_toc_file_tmp2 = full_toc_file+'.tmp2'      
    remove_book_tags(full_toc_file_tmp1, full_toc_file_tmp2)

    # Update link to first file
    insert_toc_into_book(full_toc_file_tmp2, book_file)
       
    sys.exit(0)


if __name__ == "__main__":
   main(sys.argv[1:])
