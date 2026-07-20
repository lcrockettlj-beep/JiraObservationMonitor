(function(){
  function normaliseText(value){
    return String(value || '').replace(/\s+/g, ' ').trim().toLowerCase();
  }

  function closestCard(node){
    if(!node || !node.closest){ return null; }
    return node.closest('.jom-card, .cc-card, .command-card, .metric-card, .jom-metric-card, .metric, section, article, div');
  }

  function findCardByHeading(label){
    var wanted = normaliseText(label);
    var headings = Array.prototype.slice.call(document.querySelectorAll('h1,h2,h3,h4,h5,h6,strong,p,span,div'));
    for(var i=0;i<headings.length;i++){
      var text = normaliseText(headings[i].textContent);
      if(text === wanted || text.indexOf(wanted) === 0){
        var card = closestCard(headings[i]);
        if(card){ return card; }
      }
    }
    return null;
  }

  function applyMetricLayoutRepair(){
    var coverageCard = findCardByHeading('Monitoring Coverage');
    var dataHealthCard = findCardByHeading('Data Health');
    var estateCard = findCardByHeading('Estate');
    var monitoredCard = findCardByHeading('Monitored');

    if(!coverageCard){ return; }
    coverageCard.classList.add('jom-monitoring-coverage-card');

    var metricParent = null;
    if(dataHealthCard && dataHealthCard.parentElement){ metricParent = dataHealthCard.parentElement; }
    else if(monitoredCard && monitoredCard.parentElement){ metricParent = monitoredCard.parentElement; }
    else if(estateCard && estateCard.parentElement){ metricParent = estateCard.parentElement; }

    if(metricParent && coverageCard.parentElement !== metricParent){
      metricParent.appendChild(coverageCard);
    }

    if(metricParent){
      metricParent.classList.add('jom-command-centre-metrics-fixed');
      metricParent.setAttribute('data-jom-command-metric-layout','fixed-v1');
    }
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', applyMetricLayoutRepair, { once: true });
  } else {
    applyMetricLayoutRepair();
  }
  window.setTimeout(applyMetricLayoutRepair, 350);
  window.setTimeout(applyMetricLayoutRepair, 1000);
})();
