#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Builds OpenPOWER Foundation documentation using standard template.
#
# Assumes rst2db has been used to convert rst to docbook.
#
import os, sys, getopt, shutil, errno, subprocess, copy, re
from os import fdopen, remove
from shutil import move
from git import Repo
from lxml import etree
from conf import opf_docbook_settings, master_doc, project
from subprocess import Popen, PIPE
    

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

def traverse_clean_html_source_examples(filename):
    temp_file = filename + '.tmp'
    code_found = False
    html_source_start_regex = '^<div class="highlight-default"><div class="highlight"><pre>'
    html_source_stop_regex = '^</pre></div>'
    span_regex = '\<span(\sclass="[a-z]+")?>'

    print filename
    
    # Walk file by line
    with open(temp_file, 'w') as new_file:
        with open(filename) as old_file:
            for line in old_file:
                if re.match(html_source_start_regex,line):
                    # print 'DEBUG: Code block start found'
                    code_found = True
                elif re.match(html_source_stop_regex,line):
                    # print 'DEBUG: Code block stop found'
                    code_found = False

                if code_found:
                    oldline = line
                    # Remove </span> references
                    line = line.replace('</span>', '')
                    # Remove <span class=...> references
                    line = re.sub(span_regex, '', line)
                    # print 'DEBUG: line changed.\n  Old: >' + oldline + '<\n  New: >' + line + '<'
                new_file.write(line)

    # Preserve old file
    move(filename, filename + '.bak')
    
    # Move new file into old
    move(temp_file, filename)

def traverse_clean_html_nodes(element):

    if 'ul' in element.tag and element.attrib:
        key = element.attrib.keys()[0]
        value = element.attrib[key]
        if 'id' in key:
            first_child = element.__getitem__(0);
            if first_child.__len__() == 0:
                print 'Error: Bad assumption. <ul> tag is empty.'
                
            # Add attribute to first_child and remove from element
            first_child.attrib[ key ] = value;
            del element.attrib[ key ]
            
            # print 'DEBUG: <ul> attributes: ', element.attrib
            # print 'DEBUG: child attributes: ', first_child.attrib
            sys.stderr.write( '**Information: id attribute on <ul> tag to first sub-element, <' + element.tag + '> for ' + key + ' = ' + value + '\n' )
    
    for child in element.getchildren():
        traverse_clean_html_nodes(child)

def cleanup_html(infile, outfile):
 
    # Create internal representation of document from infile
    parser = etree.XMLParser(remove_comments=False)    
    tree = etree.parse(infile, parser=parser)
    head = tree.getroot()

    # print_tree( head, 0, 2 )    

    # Walk nodes doing any cleanup
    traverse_clean_html_nodes(head)

    # Persist updates to output file
    tree.write(outfile)
    
    # Note: This invocation needs to occur post tree-write because
    #       it will update file
    traverse_clean_html_source_examples(outfile)
        
def find_match(reference, anchor_node, relationship):

    if not anchor_node is None and 'anchor' in anchor_node.tag:
        # Try this, verify matching ids
        key = anchor_node.attrib.keys()[0]
        value = anchor_node.attrib[key]
        regex = '^' + reference + '(\.\d+)?$'

        # print 'DEBUG: ' + relationship + ' anchor check.  Reference: ' + reference + ' Regex: ' + regex + ' Value: ' + value

        if re.match(regex,value):
            return anchor_node

        else:
            # print 'DEBUG: Anchor in ' + relationship + ' tag does not match.  Expected: ', reference, ' Found: ', value, ' Looking further...'
            node = anchor_node
            while not node.getprevious() is None:
                node = node.getprevious()
                if 'anchor' in node.tag:
                    key = node.attrib.keys()[0]
                    value = node.attrib[ key ]
                    if re.match(regex,value):
                        # print 'DEBUG: Anchor in ' + relationship + ' tag finally match!!!'
                        return node
                    # else
                        # print 'DEBUG: Anchor in ' + relationship + ' tag does not match.  Expected: ', reference, ' Found: ', value, ' Looking further...'

                else:
                    # print 'DEBUG: Anchor in ' + relationship + ' tag does not match.  Expected: ', reference, ' Found: ', value, ' Anchor node: ', node
                    return None

    else:
        # print 'Error: find_match called with non-anchor element.  Reference: ' + reference + ' Node: ' + anchor_node + ' Relationship: ' + relationship
        return None

def traverse_clean_links(element):

    if 'link' in element.tag:
        # Note: Terminal tag, no need to recurse
        
        # Gather link details
        text = element.text
        num_attributes = element.attrib.__len__()
        reference = element.attrib.get('linkend',None)
        
        if num_attributes is 1 and not reference is None and text == u'¶':
            # Erroneous link message, find related anchor, could be "uncle" or "cousin" (of various degrees)
            anchor = None
            parent = element.getparent()
            grandparent = parent.getparent()
            greatuncle = grandparent.getprevious()
            
            # Check Great Uncle for match
            anchor = find_match(reference, greatuncle, 'Great Uncle')
            
            # If no match, locate "cousin" and if found, check it
            if anchor is None:
                cousin = None
                if not greatuncle is None:
                    node = greatuncle
                    while node.__len__() > 0 and cousin is None:
                        node = node.__getitem__(node.__len__() -1)
                        if 'anchor' in node.tag:
                            cousin = node
                
                if not cousin is None:
                    anchor = find_match(reference, cousin, 'Cousin')
                
            # If no match, try uncle
            if anchor is None:
                uncle = parent.getprevious()
                anchor = find_match(reference, uncle, 'Uncle')
                        
            # Always delete <link> tag of this type (contains only u'¶' for text)
            parent.__delitem__(parent.index(element))
            
            if not anchor is None:
                # print 'MATCH FOUND: ', reference

                # Retrieve attribute key from anchor
                # Note: The <link> key is always correctly set by herold in the case of duplicate keys.  
                #       The <anchor> tag may have a "dot" and a number appended to value in <link>.
                key = anchor.attrib.keys()[0]
                value = anchor.get(key)
                if 'title' in parent.tag:
                    # Add id attribute to Grandparent
                    grandparent.set(key,value)
                else:
                    # Add id attribute to Parent
                    parent.set(key,value)
                    
                sys.stderr.write( '**Information: removed dummy link and for ' + reference + ' and added proper xml:id as ' + value + '\n' )
                    
                # Delete <anchor> tag
                anchor_parent = anchor.getparent()
                anchor_parent.__delitem__(anchor_parent.index(anchor))
            else:
                # Nothing more to do
                sys.stderr.write( '**Information: Matching <anchor> element not found for reference = ' + reference + '.  Link removed.' + '\n' )
                
     
    else: 
        for child in element.getchildren():
            traverse_clean_links(child)

def traverse_clean_other(element):
    if 'informalexample' in element.tag:
        # Get key elements around this one        
        parent = element.getparent()
        grandparent = parent.getparent()

        # Create new elements -- section and title (use text from informal example element)
        new_section = parent.makeelement(grandparent.tag)
        new_title = parent.makeelement('title')
        title = element.text
        new_title.text = title

        # Add title to new section
        new_section.append(new_title)

        # Copy over children from <informalexample> to new <section>
        for child in element.getchildren():
            element.remove(child)
            new_section.append(child)

        # print 'DEBUG: old tree...'
        # print_tree(parent, 0, 2)

        # Add new <section> as next sibling of parent and remove <informalexample> from parent
        parent.addnext(new_section)
        parent.remove(element)

        # print 'DEBUG: new tree...'
        # print_tree(parent.getparent(), 0, 3)
        
        sys.stderr.write( '**Information: <informalexample> ' + element.text + ' removed and promoted as <section> with title: ' + title + '\n' )

    elif 'note' in element.tag:
        # Get key elements around this one        
        parent = element.getparent()
        grandparent = parent.getparent()

        # print 'DEBUG: old tree...'
        # print_tree(parent, 0, 4)

        # Create new elements -- section and title (use text from bridgehead subelement)
        new_section = parent.makeelement(parent.tag)        
        bridgehead = element.__getitem__(0).__getitem__(0)
        
        if not 'bridgehead' in bridgehead.tag:
            print 'Error: Bad assumption about <note> structure.  Bridgehead not found as expected.'
            sys.exit(-20)
        
        title = bridgehead.text    
        new_title = parent.makeelement('title')
        new_title.text = title

        # Add title to new section
        new_section.append(new_title)
        
        # Remove <bridgehead> from <note>
        bridgehead.getparent().remove(bridgehead)
        
        # Copy over remaining items in <note> to new <section>
        for child in element.getchildren():
            element.remove(child)
            new_section.append(child)
        
        # Add new <section> as next sibling of parent and remove <note> from parent
        parent.addnext(new_section)
        parent.remove(element)

        # print 'DEBUG: New tree...'
        # print_tree(grandparent, 0, 3)
       
        sys.stderr.write( '**Information: <note> removed and promoted as <section> with title: ' + title + '\n' )

    elif 'anchor' in element.tag:
        # Get key elements around this one        
        parent = element.getparent()

        # Retrieve anchor details
        key = element.attrib.keys()[0]
        value = element.attrib[ key ]

        # Remove node        
        parent.remove( element );

        sys.stderr.write( '**Information: removed <anchor> with id: ' + value + '\n' )
    
    elif 'section' in element.tag:
        #Ensure at least one child beyond <title>
        if element.__len__() == 1:
            title = element.__getitem__(0).text
            parent = element.getparent()

            # Make and add empty paragraph to section, just behind title
            new_para = parent.makeelement('para')
            new_para.text = '&nbsp;'
            element.append(new_para)            
                   
            sys.stderr.write( '**Information: <para> tag added to empty section with title: ' + title + '\n' )

    for child in element.getchildren():
        traverse_clean_other(child)

def cleanup_xml(infile, outfile):
    # Create internal representation of document from infile
    parser = etree.XMLParser(remove_comments=False)    
    tree = etree.parse(infile, parser=parser)
    head = tree.getroot()

    # print_tree( head, 0, 2 )    

    # Note: because link cleanup involves relative location of multiple tags, it must be separate and first
    traverse_clean_links(head)
    traverse_clean_other(head)

    # Persist updates to output file
    tree.write(outfile)
        
def print_tree(element, level, max_depth):
    # Print current element
    num_children = element.__len__()
    indent = ' '.ljust(level+1)
    
    if level < max_depth:
        print indent, 'Tag: ', element.tag, ' Attrib: ', element.attrib, ' Text: >', element.text, '< Num children: ', num_children
        
        for i in range(num_children):
            child = element.__getitem__(i)
            print_tree(child, level+1, max_depth)

def traverse_clean_sections(element):
    section_blacklist = ['Navigation', 'Table Of Contents']

    # Walk children looking for next set of <section> tags, opening include files if necessary
    num_children = element.__len__()
    i = 0;
    while i < num_children:
        child = element.__getitem__(i)
        parent = element
        
        # print 'DEBUG: clean sections, visiting node with tag: ' + child.tag
        
        # Walk first level of tags, deleting info and any "blacklist" sections
        if 'section' in child.tag:
            num_sec_children = child.__len__()
            
            title = ''
            if num_sec_children > 0:
                first_grandchild = child.__getitem__(0)
                if first_grandchild.__len__() == 0:
                    title = child.__getitem__(0).text
                else:
                    # This makes me nervous, not sure how well it will work...
                    title = first_grandchild.__getitem__(0).text
                # print 'Section title found: ' + title
            
            if title in section_blacklist:
                # Delete section
                # print 'DEBUG: Deleted blacklist section ' + title
                parent.remove(child)
                num_children = num_children-1
            else:
                traverse_clean_sections(child)
                i = i+1
        else:
            i=i+1
    
def eliminate_top_section(head):

    # Remove <info> and <index> sections
    for child in head.getchildren():
        if 'info' in child.tag or 'index' in child.tag:
            # print 'DEBUG: unneeded top level tag: ' + child.tag
            head.remove(child)
    
    # Eliminate head section which really is title
    if head.__len__() == 1:
        first_section = head.__getitem__(0)
        
        if not 'section' in first_section.tag:
            print 'Error: Bad assumption.  Top tag in document is not a section.'
            sys.exit(-36) 
                   
        # print 'DEBUG: first section -- tag: ' + first_section.tag + ' num children: ' + str(first_section.__len__())
        
        for child in first_section.getchildren():
            # print 'DEBUG: child -- tag: ' + child.tag + ' num children: ' + str(child.__len__())
            
            # Promote sections
            if 'section' in child.tag:
                first_section.remove(child);
                head.append(child);
                # print 'DEBUG: Promoting child -- tag: ' + child.tag
        
        head.remove(first_section)

    else:
        print 'Error: Bad assumption.  Too many sections (' + str(head.__len__()) + ') found in base document.'
        sys.exit(-13)


def transform_head_sections(head):

    num_chapter = 0
    
    for child in head.getchildren():
        if 'section' in child.tag:
            child.tag = child.tag.replace('section','chapter')
            num_chapter = num_chapter+1

    if num_chapter == 0:
        print 'Error: No chapters found in document'
        sys.exit(-6)        


def convert_structure(infile, outfile):

    # Create internal representation of document from infile
    parser = etree.XMLParser(remove_comments=False)    
    tree = etree.parse(infile, parser=parser)
    head = tree.getroot()

    # print 'DEBUG: Pre tree structure cleanup...'        
    # print_tree(head, 0, 3)

    if 'article' in head.tag:
        head.tag = 'book'
        
        # Clear attributes
        for attrib in head.attrib.keys():
            head.attrib.pop(attrib, None)
        if head.attrib.items() != []:
            print 'Error: Section attributes not removed. ', head.attrib.items(), ' items remain -- ', head.attrib.keys()
            sys.exit(-5)
    else:
        print 'Toc file contains ', head.tag, 'tag, not <article>'
        sys.exit(-4)

    # Traverse tree sections, removing nodes as needed
    traverse_clean_sections(head)

    # Eliminate first section, placeholder for document title
    eliminate_top_section(head)
        
    # Traverse remaining top level <section> and convert to <chapter>
    transform_head_sections(head)

    # print 'DEBUG: Post tree structure cleanup...'        
    # print_tree(head, 0, 2)
                        
    # Persist updates to output file
    tree.write(outfile)


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

def build_revhistory(book_file):
    # Variables for formating git log
    log_format = '%h%x01%an%x01%ad%x01%s%x02'
    log_fields = ['id', 'author', 'date', 'subject']

    # Retrieve log
    pipe = Popen('git log --date=iso --format="%s" -- . .' % log_format, shell=True, stdout=PIPE)
    log, _ = pipe.communicate()
    
    # Substitute for problem characters: &, <, >
    log = log.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
    
    # Remove newlines, trailing end-of-record (0x02), and then split at end-of-record
    log = log.replace('\n','').strip('\x02').split('\x02')
    
    # Split records into individual fields
    log = [row.split('\01') for row in log]
    
    # Create dictionary using field names
    log = [dict(zip(log_fields, row)) for row in log]

    # Format log into revision history    
    revision = '<revhistory>\n'
    for entry in log:
        revision = revision + '<revision><date>' + entry['date'].split(' ')[0] + '</date><revdescription><para>' +\
            entry['subject'] + ' (' + entry['id'] + ')</para></revdescription></revision>\n'
    revision = revision + '</revhistory>\n'

    # Update file
    rev_str = '<revhistory>TBD</revhistory>'
    update_file(book_file, rev_str, revision)

    
def main(argv):
    master_git_url = 'https://github.com/OpenPOWERFoundation/Docs-Master.git'    
    template_git_url = 'https://github.com/OpenPOWERFoundation/Docs-Template.git'    
    html_dir = ''
    build_dir = ''
    db_dir = ''
    master_dir = ''
    template_dir = ''
    toc_file = master_doc+'.xml'

    try:
        opts, args = getopt.getopt(argv,"hs:b:d:m:t:",["htmldir","builddir=","docbookdir=","masterdir=","templatedir="])
    except getopt.GetoptError:
        print 'Invalid option specified.  Usage:'
        print '    opf_html2db.py -s <htmldir> -b <builddir> -d <docbookdir> -m <masterdir> -t <templatedir>'
        sys.exit(-1)
    for opt, arg in opts:
        if opt == '-h':
           print 'opf_hmtl2db.py -s <htmldir> -b <builddir> -d <docbookdir> -m <masterdir> -t <templatedir>'
           sys.exit(0)
        elif opt in ("-s", "--htmldir"):
           html_dir = arg
        elif opt in ("-b", "--builddir"):
           build_dir = arg
        elif opt in ("-d", "--docbookdir"):
           db_dir = arg
        elif opt in ("-m", "--masterdir"):
           master_dir = arg
        elif opt in ("-t", "--templatedir"):
           template_dir = arg

		# Verify html directory, error if not found
    if not os.path.exists(html_dir):
        print 'ERROR: ' + html_dir  + ' does not exist.  Please specify path to directory containing single html file.'
        sys.exit(-11)

    # Generate path to single file
    # NOTE: assumption is that file name is always "index.html" (master_doc).  If this doesn't prove true, may need to use variable.
    html_file_src = os.path.join(html_dir, master_doc + '.html')

    if not os.path.isfile(html_file_src):
        print 'ERROR: ' + html_file_src  + ' does not exist.  Please verify path to single html file and file name.'
        sys.exit(-12)

    # Convert html file to xml and place in db directory
    if not os.path.exists(db_dir):
        print 'Making docbook build directory ' + db_dir
        os.path.makedirs(db_dir)

    db_file = os.path.join(db_dir, project + '.xml')    
    if os.path.exists(db_file):
        os.remove(db_file)

    # Clean up herold html output
    print 'Cleaning up html file before processing'
    html_file = os.path.join(db_dir, master_doc + '.html')
    html_file_tmp1 = html_file + '.tmp1'
    shutil.copy2(html_file_src, html_file)
    cleanup_html(html_file, html_file_tmp1)

    print 'Converting html file to XML...'        
    print subprocess.check_output(['herold', '-i', html_file_tmp1, '-o', db_file])
    
    # Clone a new Master Directory
    print 'Cloning new Docs-Master directory...'
    if os.path.exists(master_dir):
        shutil.rmtree(master_dir)
    Repo.clone_from(master_git_url, master_dir)
    
    # Clone a new Template Directory
    print 'Cloning new Docs-Template directory...'
    if os.path.exists(template_dir):
        shutil.rmtree(template_dir)
    Repo.clone_from(template_git_url, template_dir)
    
    # Create the new XML file  *****
    rst_template_dir = os.path.join(template_dir, 'rst_template') 
    full_toc_file = os.path.join(rst_template_dir,  toc_file)
    shutil.copy2(db_file, full_toc_file)
    book_file = os.path.join(rst_template_dir,  'bk_main.xml')
    
    # Update all file in opf_docbook_settings with tag/value combinations specified
    print 'Updating Docbook files with settings from conf.py...'
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
    print 'Cleaning up Docbook file structure...'
    full_toc_file_tmp1 = full_toc_file+'.tmp1'  
    full_toc_file_tmp2 = full_toc_file+'.tmp2'  
    full_toc_file_tmp3 = full_toc_file+'.tmp3'  

    # Walk document correcting XML errors
    cleanup_xml( full_toc_file, full_toc_file_tmp1 )
    
    # Remove extraneous sections
    convert_structure( full_toc_file_tmp1, full_toc_file_tmp2 )
    
    # Eliminate <book> and <title> tags in .tmp1 and write to .tmp2 file
    remove_book_tags(full_toc_file_tmp2, full_toc_file_tmp3)

    # Update link to first file
    insert_toc_into_book(full_toc_file_tmp3, book_file)
    
    # Create revision history from Git Log
    print 'Building document revision history from git log...'
    build_revhistory(book_file)

    # TODO: Remove this hack after rst_template bk_main gets updated
    update_file(book_file, 'xmlns:xlink', 'xmlns:xl')
                
    # Perform build of Docbook
    print 'Building Docbook PDF and HTML output in Maven...'
    maven_log_file = 'build.log'
    maven_build = 'cd ' + rst_template_dir + '; mvn generate-sources 2>&1 | tee ' + maven_log_file + ''
    pipe = Popen(maven_build, shell=True)
    log, err = pipe.communicate()
    
    if pipe.returncode != 0:
        print "Build failed with return code:%s" % pipe.returncode
        print "See %s/build.log for more details" & rst_template_dir
    
    # Copy output to better location
    print 'Copying build output...'
    bld_out_dir = os.path.join(rst_template_dir, 'target/docbkx/webhelp')
    html_head = os.path.join(bld_out_dir, opf_docbook_settings['pom.xml']['webhelpDirname'] + '/index.html')
    if os.path.exists(bld_out_dir) and os.path.exists(html_head):
        doc_dir = os.path.join(build_dir, 'docbook/opf_docbook')
        
        if os.path.exists(doc_dir):
            shutil.rmtree(doc_dir)
        shutil.copytree(bld_out_dir, doc_dir)
        print "Build successful.  Output files located in %s" % os.path.join(doc_dir, opf_docbook_settings['pom.xml']['webhelpDirname'])
       
        sys.exit(0)

    else:
        print "Docbook build failed.  Check logfile %s for details." % os.path.join(rst_template_dir, maven_log_file)
        sys.exit(-10)

if __name__ == "__main__":
   main(sys.argv[1:])
