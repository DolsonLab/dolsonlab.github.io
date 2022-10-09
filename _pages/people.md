---
permalink: /people
layout: article
---

# Current Lab Members

  <div class="article-list grid grid--p-3">
    {% for person in site.data.authors %}

    {%- unless person.enddate -%}
    <div class="cell cell--12 cell--md-4 cell--lg-4">
        <div class="card">
            {%- if person.avatar -%}
                <div class="card__image person_image"><img src="{{ person.avatar }}" /></div>
            {%- endif -%}
            <div class="card__content">
                <header>
                    <a href="{{ person.url }}"><h2 class="card__header">{{ person.name }}</h2></a>
                </header>
                <h4>{{ person.role }}</h4>
                <h5>{{person.affiliation}}</h5>
                <p>{{ person.bio }}</p>
                <div class="footer__author-links">
                    {% include author-links.html author=person %}
                </div>    
            </div>
        </div>
    </div>

    {% endunless %}
    {% endfor %}
</div>

<br><br> 

# Lab Alumni

  <div class="article-list grid grid--p-3">
    {% for person in site.data.authors %}

    {%- if person.enddate -%}
    <div class="cell cell--12 cell--md-4 cell--lg-4">
        <div class="card">
            {%- if person.avatar -%}
                <div class="card__image person_image"><img src="{{ person.avatar }}" /></div>
            {%- endif -%}
            <div class="card__content">
                <header>
                    <a href="{{ person.url }}"><h2 class="card__header">{{ person.name }}</h2></a>
                </header>
                <h4>{{ person.role }}</h4>
                <h5>{{person.affiliation}}</h5>
                <h6>{{ person.startdate | date: '%B %Y' }} - {{ person.enddate | date: '%B %Y' }}</h6>
                <p>{{ person.bio }}</p>
                <div class="footer__author-links">
                    {% include author-links.html author=person %}
                </div>    
            </div>
        </div>
    </div>

    {% endif %}
    {% endfor %}
</div>