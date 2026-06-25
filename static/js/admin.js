const humanUsers=61; const jiraSeats=139;
const ratio=(jiraSeats/humanUsers).toFixed(2);
document.getElementById('identity').innerText=`Humans: ${humanUsers}`;
document.getElementById('billing').innerText=`Jira Seats: ${jiraSeats}`;
document.getElementById('insight').innerText=`Seat/User Ratio: ${ratio}`;
