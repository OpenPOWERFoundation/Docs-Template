# Master Template Document Project for OpenPOWER Foundation Documentation
This repository hold the source for the master document template for 
OpenPOWER Foundation. The PDF and HTML generated from the doc/template/ 
directory build a document that both describes how to build a new
document and contains examples and directions on how to do it.

To build this project, one must ensure that the Docs-Master project has
also been cloned at the same directory level as the Docs-Template project.
This can be accomplished with the following steps:

1. Clone this project (Docs-Master) using the following command:
```
$ git clone https://github.com/OpenPOWERFoundation/Docs-Master.git
```
2. Clone the documentation project (my_project) using the following command:
```
$ git clone https://github.com/OpenPOWERFoundation/my_project.git
```
3. Build the project with these commands:
```
$ cd Docs-Template
$ mvn clean generate-sources
```

The online version of the document can be found in the OpenPOWER Foundation
Document library at [TBD](http://openpowerfoundation.org/docs)

The project which control the look and feel of the document is the 
[Docs-Maven-Plugin project](https://github.com/OpenPOWERFoundation/Docs-Maven-Plugin).

To contribute to the OpenPOWER Foundation template document project, contact Jeff Scheel \([scheel@us.ibm.com](mailto://scheel@us.ibm.com)\) or 
Jeff Brown \([jeffdb@us.ibm.com](mailto://jeffdb@us.ibm.com)\).
