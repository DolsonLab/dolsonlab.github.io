---
permalink: /people
layout: article
---

# Current Lab Members

  <div class="article-list grid grid--p-3">
  {% assign pi = site.data.authors | sort: "startdate" | where: "role", "Principal Investigator"  %}
  {% assign grads = site.data.authors | sort: "startdate" | where: "role", "PhD Student" %}
  {% assign ugs = site.data.authors | sort: "startdate" | where: "role", "Undergraduate Researcher" %}

  {% assign people = pi | concat: grads | concat: ugs | concat: site.data.authors | uniq | where: "enddate", nil %}
  {% for person in people %}
    
    {% include person.html %}

  {% endfor %}
</div>

<br><br> 

# Lab Alumni

  <div class="article-list grid grid--p-3">
    {% assign people = pi | concat: grads | concat: ugs | concat: site.data.authors | uniq %}

    {% assign people_with_enddate = people | where_exp: "person", "person.enddate != nil" %}

    {% for person in people_with_enddate %}
        {% include person.html %}
    {% endfor %}
</div>