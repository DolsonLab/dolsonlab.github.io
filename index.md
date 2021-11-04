---
layout: landing
title: The ECODE Lab 
excerpt: >
  Evolutionary Control of Digital Ecologies
mode: immersive
# aside:
  # toc: true
header:
  background: "#000000"
#   theme: dark
article_header:
  type: overlay
  theme: dark
  align: center
  # background_color: '#000000'
  background_image:
    # gradient: 'linear-gradient(135deg, rgba(34, 139, 87, .4), rgba(0, 0, 0, .4))'
    src: /assets/images/spatialphylogeny.png
  actions:
    - text: Our Research
      type: outline-theme-dark
      url: "#hero-1"
    # - text: Principal Investigator
    #   url: "#hero-2"

data:
  sections:
    - title: Our Research
      excerpt: "The world is filled with ecological communities made up of multiple evolving populations. Controlling the trajectory of evolution in these communities is a general problem that is important in contexts ranging from medicine to machine learning. In the ECODE (Evolutionary Control of Digital Ecologies) lab, we are an interdisciplinary group of researchers coming at this problem from a range of different perspectives. Our core tool is digital evolutionary experiments, but we embrace many other approaches where appropriate, including pure mathematical theory, collaborations with wet lab researchers, and re-analysis of previously published field data. While some of our work is very abstract, we usually try to ground our research in specific communities that we would like to steer the evolution of. That way our findings have immediate relevance to those problems, but also inform our general quest for evolutionary control. Some specific problems that we are interested in include:"
      children:
      - title: Evolutionary Computation
        image:
          src: /assets/images/General_EC_Diagram.png
      - title: Microbiome Communities
        image:
          src: /assets/images/symbulation.png  
      - title: Cancer
        image:
          src: /assets/images/memic.png 
      - title: Data Analysis Tools
        image:
          src: /assets/images/Phylogenyschematic.png
      # - title: Climate Change
      #   image:
      #     src: /assets/images/symbulation.png            
    - title: Lab Members
      excerpt: Members of the ECODE lab come from a wide diversity of backgrounds ranging from biology to computer science.
      # theme: dark
      actions:
        - text: People
          url: /people.html
      image:
        is_row: true
        full_width: true
        style: "max-width: 960px;"
        src: /assets/images/lab_photo_corn_maze_2021.jpg
      actions:
        - text: People
          url: /people.html
      # background_color: "#000000"
    # - title: Super Customizable
    #   excerpt: Everything from the menus, sidebars, comments, and more can be configured or set with YAML Front Matter.
    #   actions:
    #     - text: See Examples
    #       url: /samples.html
    #     - text: Learn More
    #       url: /docs/en/configuration
---