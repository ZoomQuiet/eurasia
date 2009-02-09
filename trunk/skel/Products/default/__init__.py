def controller(client):
	client['Content-Type'] = 'text/html'
	client.write(page)
	client.close()

page = '''\
<html>
<head>
<title>Eurasia3 Default Page</title>
</head>
<body>
<h1>It works!</h1>
</body>
</html>'''
